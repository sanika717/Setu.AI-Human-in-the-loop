from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(String(length=64), unique=True, nullable=False, index=True)
    applicant_id = Column(String(length=128), nullable=False, index=True)
    service_id = Column(String(length=64), nullable=True)
    status = Column(String(length=32), nullable=False, default="draft")
    otp_verified = Column(Boolean, nullable=False, default=False)
    submission_hash = Column(String(length=64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    fields = relationship(
        "GovernedField", back_populates="application", cascade="all, delete-orphan", lazy="selectin"
    )
    audit_entries = relationship(
        "AuditLogEntry", back_populates="application", cascade="all, delete-orphan", lazy="selectin",
        order_by="AuditLogEntry.sequence_number",
    )
    otp_challenges = relationship(
        "OtpChallenge", back_populates="application", cascade="all, delete-orphan", lazy="selectin",
        order_by="OtpChallenge.created_at",
    )
    final_submission = relationship(
        "FinalSubmission", back_populates="application", uselist=False, cascade="all, delete-orphan",
    )
    trusted_delegates = relationship(
        "TrustedDelegate", back_populates="application", cascade="all, delete-orphan", lazy="selectin",
        order_by="TrustedDelegate.created_at",
    )


class GovernedField(Base):
    __tablename__ = "governed_fields"
    __table_args__ = (UniqueConstraint("application_id", "field_name", name="uq_application_field"),)

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    field_name = Column(String(length=128), nullable=False)
    original_value = Column(Text, nullable=True)
    current_value = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    confidence_level = Column(String(length=32), nullable=True)
    source_document = Column(String(length=128), nullable=True)
    reason = Column(Text, nullable=True)
    is_required = Column(Boolean, nullable=False, default=True)
    decision_status = Column(String(length=16), nullable=False, default="pending")
    is_edited = Column(Boolean, nullable=False, default=False)
    decision_note = Column(Text, nullable=True)
    decided_by = Column(String(length=128), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    application = relationship("Application", back_populates="fields")


class AuditLogEntry(Base):
    __tablename__ = "audit_log_entries"
    __table_args__ = (
        UniqueConstraint("application_id", "sequence_number", name="uq_application_sequence"),
    )

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    sequence_number = Column(Integer, nullable=False)
    action = Column(String(length=64), nullable=False)
    field_name = Column(String(length=128), nullable=True)
    actor = Column(String(length=128), nullable=False)
    details = Column(Text, nullable=True)  # canonical JSON string
    previous_hash = Column(String(length=64), nullable=False)
    entry_hash = Column(String(length=64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    application = relationship("Application", back_populates="audit_entries")


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    destination = Column(String(length=256), nullable=True)
    otp_hash = Column(String(length=128), nullable=False)
    salt = Column(String(length=64), nullable=False)
    delivery_channel = Column(String(length=32), nullable=False, default="console")
    attempts_remaining = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verified = Column(Boolean, nullable=False, default=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    application = relationship("Application", back_populates="otp_challenges")


class FinalSubmission(Base):
    __tablename__ = "final_submissions"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), unique=True, nullable=False, index=True)
    submitted_by = Column(String(length=128), nullable=False)
    submission_hash = Column(String(length=64), nullable=False)
    field_snapshot = Column(Text, nullable=False)  # canonical JSON string
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    application = relationship("Application", back_populates="final_submission")


class TrustedDelegate(Base):
    """Phase F (Human-in-the-Loop): an optional Trusted Person (family
    member, caregiver, NGO volunteer) an applicant can name to additionally
    approve an application before it can be submitted - on top of, never
    instead of, OTP verification. Registering a delegate records the
    applicant's explicit consent to share this specific application with
    that specific person (Phase G: consent is scoped, not blanket).

    Only one delegate can be "active" (i.e. gate submission) per
    application at a time; registering a new one revokes the previous one
    (`revoked_at` set) rather than deleting history, so the audit trail of
    who was ever trusted stays intact.
    """

    __tablename__ = "trusted_delegates"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    delegate_name = Column(String(length=128), nullable=False)
    relationship_to_applicant = Column(String(length=64), nullable=False)
    contact = Column(String(length=256), nullable=False)
    approval_required = Column(Boolean, nullable=False, default=True)
    consent_given_by = Column(String(length=128), nullable=False)
    consent_given_at = Column(DateTime(timezone=True), nullable=False)
    approved = Column(Boolean, nullable=False, default=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    application = relationship("Application", back_populates="trusted_delegates")
