import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Application, GovernedField
from ..models.enums import AuditAction, ReportFormat
from ..models.request_models import (
    ApplicationCreateRequest,
    FieldApproveRequest,
    FieldEditRequest,
    FieldRejectRequest,
    OTPRequestRequest,
    OTPVerifyRequest,
    SubmitApplicationRequest,
    TrustedDelegateApproveRequest,
    TrustedDelegateRegisterRequest,
    TrustedDelegateRevokeRequest,
)
from ..models.response_models import (
    ApplicationResponse,
    ApplicationStatusResponse,
    ApplicationSummary,
    AuditChainVerificationResponse,
    AuditLogEntryResponse,
    FinalSubmissionResponse,
    GovernedFieldResponse,
    OTPRequestResponse,
    OTPVerifyResponse,
    SubmissionValidationResponse,
    TrustedDelegateResponse,
)
from ..models.enums import FieldDecisionStatus
from ..services.audit_service import AuditService
from ..services.decision_service import DecisionService
from ..services.delegate_service import DelegateService
from ..services.otp_service import OTPService
from ..services.report_service import ReportService
from ..services.submission_service import SubmissionService
from ..utils.exceptions import (
    ApplicationLockedError,
    ApplicationNotFoundError,
    FieldNotFoundError,
    GovernanceError,
    InvalidApplicationStateError,
    OTPExpiredError,
    OTPInvalidError,
    OTPLockedError,
    OTPNotFoundError,
    SubmissionBlockedError,
    TrustedDelegateNotFoundError,
)
from .dependencies import get_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Error mapping — every domain exception becomes a well-formed HTTP response
# instead of leaking as a 500.
# ---------------------------------------------------------------------------

def _raise_for(exc: GovernanceError) -> None:
    if isinstance(exc, ApplicationNotFoundError) or isinstance(exc, FieldNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ApplicationLockedError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, InvalidApplicationStateError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, OTPNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, TrustedDelegateNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, OTPExpiredError):
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    if isinstance(exc, OTPLockedError):
        raise HTTPException(status_code=423, detail=str(exc)) from exc
    if isinstance(exc, OTPInvalidError):
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if isinstance(exc, SubmissionBlockedError):
        raise HTTPException(status_code=409, detail="; ".join(exc.reasons)) from exc
    raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Response builders — map ORM objects to response models. Written by hand
# (rather than relying on from_attributes alone) because a couple of field
# names intentionally differ between the DB model and the API contract
# (e.g. `is_required` -> `required`).
# ---------------------------------------------------------------------------

def _field_to_response(field: GovernedField) -> GovernedFieldResponse:
    return GovernedFieldResponse(
        field=field.field_name,
        original_value=field.original_value,
        current_value=field.current_value,
        confidence=field.confidence,
        confidence_level=field.confidence_level,
        source_document=field.source_document,
        reason=field.reason,
        required=field.is_required,
        decision_status=field.decision_status,
        is_edited=field.is_edited,
        decision_note=field.decision_note,
        decided_by=field.decided_by,
        decided_at=field.decided_at,
    )


def _application_to_response(application: Application) -> ApplicationResponse:
    return ApplicationResponse(
        application_id=application.application_id,
        applicant_id=application.applicant_id,
        service_id=application.service_id,
        status=application.status,
        otp_verified=application.otp_verified,
        submission_hash=application.submission_hash,
        created_at=application.created_at,
        updated_at=application.updated_at,
        submitted_at=application.submitted_at,
        fields=[_field_to_response(f) for f in application.fields],
    )


def _application_to_status_response(application: Application) -> ApplicationStatusResponse:
    pending = sum(1 for f in application.fields if f.decision_status == FieldDecisionStatus.PENDING.value)
    approved = sum(1 for f in application.fields if f.decision_status == FieldDecisionStatus.APPROVED.value)
    rejected = sum(1 for f in application.fields if f.decision_status == FieldDecisionStatus.REJECTED.value)
    return ApplicationStatusResponse(
        application_id=application.application_id,
        status=application.status,
        otp_verified=application.otp_verified,
        submitted_at=application.submitted_at,
        pending_fields=pending,
        approved_fields=approved,
        rejected_fields=rejected,
    )


def _delegate_to_response(application_id: str, delegate) -> TrustedDelegateResponse:
    return TrustedDelegateResponse(
        application_id=application_id,
        delegate_name=delegate.delegate_name,
        relationship_to_applicant=delegate.relationship_to_applicant,
        contact=delegate.contact,
        approval_required=delegate.approval_required,
        consent_given_by=delegate.consent_given_by,
        consent_given_at=delegate.consent_given_at,
        approved=delegate.approved,
        approved_at=delegate.approved_at,
        revoked_at=delegate.revoked_at,
        created_at=delegate.created_at,
    )


# ---------------------------------------------------------------------------
# Application intake, retrieval, status
# ---------------------------------------------------------------------------

@router.post("/applications", response_model=ApplicationResponse, status_code=201, tags=["Applications"])
async def create_application(payload: ApplicationCreateRequest, db: AsyncSession = Depends(get_db)):
    service = DecisionService(db)
    application = await service.create_application(payload)
    return _application_to_response(application)


@router.get("/applications", response_model=list[ApplicationSummary], tags=["Applications"])
async def list_applications(
    status: str | None = Query(None, description="Filter by application status"),
    db: AsyncSession = Depends(get_db),
):
    service = DecisionService(db)
    applications = await service.list_applications(status=status)
    return [
        ApplicationSummary(
            application_id=a.application_id,
            applicant_id=a.applicant_id,
            service_id=a.service_id,
            status=a.status,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in applications
    ]


@router.get("/applications/{application_id}", response_model=ApplicationResponse, tags=["Applications"])
async def get_application(application_id: str, db: AsyncSession = Depends(get_db)):
    service = DecisionService(db)
    try:
        application = await service.get_application(application_id)
    except GovernanceError as exc:
        _raise_for(exc)
    return _application_to_response(application)


@router.get(
    "/applications/{application_id}/status", response_model=ApplicationStatusResponse, tags=["Applications"]
)
async def get_application_status(application_id: str, db: AsyncSession = Depends(get_db)):
    service = DecisionService(db)
    try:
        application = await service.get_application(application_id)
    except GovernanceError as exc:
        _raise_for(exc)
    return _application_to_status_response(application)


# ---------------------------------------------------------------------------
# Field decisions: approve / reject / edit
# ---------------------------------------------------------------------------

@router.post(
    "/applications/{application_id}/fields/{field_name}/approve",
    response_model=ApplicationResponse,
    tags=["Field Decisions"],
)
async def approve_field(
    application_id: str, field_name: str, payload: FieldApproveRequest, db: AsyncSession = Depends(get_db)
):
    service = DecisionService(db)
    try:
        application = await service.approve_field(application_id, field_name, payload.actor, payload.note)
    except GovernanceError as exc:
        _raise_for(exc)
    return _application_to_response(application)


@router.post(
    "/applications/{application_id}/fields/{field_name}/reject",
    response_model=ApplicationResponse,
    tags=["Field Decisions"],
)
async def reject_field(
    application_id: str, field_name: str, payload: FieldRejectRequest, db: AsyncSession = Depends(get_db)
):
    service = DecisionService(db)
    try:
        application = await service.reject_field(application_id, field_name, payload.actor, payload.reason)
    except GovernanceError as exc:
        _raise_for(exc)
    return _application_to_response(application)


@router.post(
    "/applications/{application_id}/fields/{field_name}/edit",
    response_model=ApplicationResponse,
    tags=["Field Decisions"],
)
async def edit_field(
    application_id: str, field_name: str, payload: FieldEditRequest, db: AsyncSession = Depends(get_db)
):
    service = DecisionService(db)
    try:
        application = await service.edit_field(
            application_id, field_name, payload.actor, payload.new_value, payload.reason
        )
    except GovernanceError as exc:
        _raise_for(exc)
    return _application_to_response(application)


# ---------------------------------------------------------------------------
# OTP verification hooks
# ---------------------------------------------------------------------------

@router.post(
    "/applications/{application_id}/otp/request", response_model=OTPRequestResponse, tags=["OTP"]
)
async def request_otp(application_id: str, payload: OTPRequestRequest, db: AsyncSession = Depends(get_db)):
    decision_service = DecisionService(db)
    try:
        application = await decision_service.get_application(application_id)
    except GovernanceError as exc:
        _raise_for(exc)

    otp_service = OTPService(db)
    try:
        challenge, exposed_code = await otp_service.request_otp(application, payload.destination)
    except GovernanceError as exc:
        _raise_for(exc)

    return OTPRequestResponse(
        application_id=application_id,
        delivery_channel=challenge.delivery_channel,
        destination=challenge.destination,
        expires_at=challenge.expires_at,
        otp_code=exposed_code,
    )


@router.post(
    "/applications/{application_id}/otp/verify", response_model=OTPVerifyResponse, tags=["OTP"]
)
async def verify_otp(application_id: str, payload: OTPVerifyRequest, db: AsyncSession = Depends(get_db)):
    decision_service = DecisionService(db)
    try:
        application = await decision_service.get_application(application_id)
    except GovernanceError as exc:
        _raise_for(exc)

    otp_service = OTPService(db)
    try:
        await otp_service.verify_otp(application, payload.code)
    except (OTPExpiredError, OTPInvalidError, OTPLockedError, OTPNotFoundError) as exc:
        # These are expected "verification failed" outcomes, not server
        # errors — still mapped to a precise status code via _raise_for,
        # but callers typically want the structured detail message.
        _raise_for(exc)
    except GovernanceError as exc:
        _raise_for(exc)

    return OTPVerifyResponse(
        application_id=application_id,
        verified=True,
        otp_verified=True,
        detail="OTP verified successfully.",
    )


# ---------------------------------------------------------------------------
# Trusted Delegate (Phase F: Human-in-the-Loop trusted-person support)
# ---------------------------------------------------------------------------

@router.post(
    "/applications/{application_id}/delegate",
    response_model=TrustedDelegateResponse,
    status_code=201,
    tags=["Trusted Delegate"],
)
async def register_delegate(
    application_id: str, payload: TrustedDelegateRegisterRequest, db: AsyncSession = Depends(get_db)
):
    decision_service = DecisionService(db)
    try:
        application = await decision_service.get_application(application_id)
    except GovernanceError as exc:
        _raise_for(exc)

    delegate_service = DelegateService(db)
    try:
        delegate = await delegate_service.register_delegate(application, payload)
    except GovernanceError as exc:
        _raise_for(exc)

    return _delegate_to_response(application_id, delegate)


@router.get(
    "/applications/{application_id}/delegate",
    response_model=TrustedDelegateResponse,
    tags=["Trusted Delegate"],
)
async def get_delegate(application_id: str, db: AsyncSession = Depends(get_db)):
    decision_service = DecisionService(db)
    try:
        application = await decision_service.get_application(application_id)
    except GovernanceError as exc:
        _raise_for(exc)

    delegate_service = DelegateService(db)
    delegate = await delegate_service.get_active_delegate(application)
    if delegate is None:
        raise HTTPException(
            status_code=404, detail=f"No active Trusted Delegate is registered for application '{application_id}'."
        )
    return _delegate_to_response(application_id, delegate)


@router.post(
    "/applications/{application_id}/delegate/approve",
    response_model=TrustedDelegateResponse,
    tags=["Trusted Delegate"],
)
async def approve_delegate(
    application_id: str, payload: TrustedDelegateApproveRequest, db: AsyncSession = Depends(get_db)
):
    decision_service = DecisionService(db)
    try:
        application = await decision_service.get_application(application_id)
    except GovernanceError as exc:
        _raise_for(exc)

    delegate_service = DelegateService(db)
    try:
        delegate = await delegate_service.approve(application, payload.actor)
    except GovernanceError as exc:
        _raise_for(exc)

    return _delegate_to_response(application_id, delegate)


@router.post(
    "/applications/{application_id}/delegate/revoke",
    response_model=TrustedDelegateResponse,
    tags=["Trusted Delegate"],
)
async def revoke_delegate(
    application_id: str, payload: TrustedDelegateRevokeRequest, db: AsyncSession = Depends(get_db)
):
    decision_service = DecisionService(db)
    try:
        application = await decision_service.get_application(application_id)
    except GovernanceError as exc:
        _raise_for(exc)

    delegate_service = DelegateService(db)
    try:
        delegate = await delegate_service.revoke(application, payload.actor)
    except GovernanceError as exc:
        _raise_for(exc)

    return _delegate_to_response(application_id, delegate)


# ---------------------------------------------------------------------------
# Submission validation + final submission
# ---------------------------------------------------------------------------

@router.get(
    "/applications/{application_id}/submission/validate",
    response_model=SubmissionValidationResponse,
    tags=["Submission"],
)
async def validate_submission(application_id: str, db: AsyncSession = Depends(get_db)):
    decision_service = DecisionService(db)
    try:
        application = await decision_service.get_application(application_id)
    except GovernanceError as exc:
        _raise_for(exc)

    submission_service = SubmissionService(db)
    reasons = submission_service.validate(application)
    return SubmissionValidationResponse(
        application_id=application_id, can_submit=not reasons, blocking_reasons=reasons
    )


@router.post(
    "/applications/{application_id}/submit", response_model=FinalSubmissionResponse, tags=["Submission"]
)
async def submit_application(application_id: str, payload: SubmitApplicationRequest, db: AsyncSession = Depends(get_db)):
    decision_service = DecisionService(db)
    try:
        application = await decision_service.get_application(application_id)
    except GovernanceError as exc:
        _raise_for(exc)

    submission_service = SubmissionService(db)
    try:
        final_submission = await submission_service.submit(application, payload.actor)
    except GovernanceError as exc:
        _raise_for(exc)

    return FinalSubmissionResponse(
        application_id=application_id,
        submitted_by=final_submission.submitted_by,
        submission_hash=final_submission.submission_hash,
        submitted_at=final_submission.submitted_at,
        field_snapshot=json.loads(final_submission.field_snapshot),
    )


# ---------------------------------------------------------------------------
# Immutable audit log
# ---------------------------------------------------------------------------

@router.get(
    "/applications/{application_id}/audit-log",
    response_model=list[AuditLogEntryResponse],
    tags=["Audit Log"],
)
async def get_audit_log(application_id: str, db: AsyncSession = Depends(get_db)):
    decision_service = DecisionService(db)
    try:
        application = await decision_service.get_application(application_id)
    except GovernanceError as exc:
        _raise_for(exc)

    audit_service = AuditService(db)
    entries = await audit_service.list_for_application(application.id)
    return [
        AuditLogEntryResponse(
            sequence_number=entry.sequence_number,
            action=entry.action,
            field_name=entry.field_name,
            actor=entry.actor,
            details=json.loads(entry.details) if entry.details else {},
            previous_hash=entry.previous_hash,
            entry_hash=entry.entry_hash,
            created_at=entry.created_at,
        )
        for entry in entries
    ]


@router.get(
    "/applications/{application_id}/audit-log/verify",
    response_model=AuditChainVerificationResponse,
    tags=["Audit Log"],
)
async def verify_audit_log(application_id: str, db: AsyncSession = Depends(get_db)):
    decision_service = DecisionService(db)
    try:
        application = await decision_service.get_application(application_id)
    except GovernanceError as exc:
        _raise_for(exc)

    audit_service = AuditService(db)
    is_valid, first_broken, detail = await audit_service.verify_chain(application.id)
    return AuditChainVerificationResponse(
        application_id=application_id,
        is_valid=is_valid,
        entries_checked=len(application.audit_entries),
        first_broken_sequence_number=first_broken,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Report generation (CSV / JSON / PDF)
# ---------------------------------------------------------------------------

@router.get("/applications/{application_id}/report", tags=["Reports"])
async def generate_report(
    application_id: str,
    format: ReportFormat = Query(ReportFormat.JSON, description="csv, json, or pdf"),
    db: AsyncSession = Depends(get_db),
):
    decision_service = DecisionService(db)
    try:
        application = await decision_service.get_application(application_id)
    except GovernanceError as exc:
        _raise_for(exc)

    audit_service = AuditService(db)
    entries = await audit_service.list_for_application(application.id)

    report_service = ReportService()
    content, media_type, filename = report_service.generate(application, entries, format)

    await audit_service.record(
        application.id,
        AuditAction.REPORT_GENERATED,
        actor="system:report",
        details={"format": format.value},
    )
    await db.commit()

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
