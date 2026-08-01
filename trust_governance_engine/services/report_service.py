import csv
import io
import json
from datetime import datetime, timezone

from ..db.models import Application, AuditLogEntry
from ..models.enums import ReportFormat

MEDIA_TYPES = {
    ReportFormat.CSV: "text/csv",
    ReportFormat.JSON: "application/json",
    ReportFormat.PDF: "application/pdf",
}


class ReportService:
    """Builds a decision-and-audit report for an application in CSV, JSON,
    or PDF. Report contents are the same underlying data in every format:
    application metadata, every field's decision outcome, and the full
    audit trail.
    """

    def generate(
        self, application: Application, audit_entries: list[AuditLogEntry], report_format: ReportFormat
    ) -> tuple[bytes, str, str]:
        if report_format == ReportFormat.CSV:
            content = self._build_csv(application)
        elif report_format == ReportFormat.JSON:
            content = self._build_json(application, audit_entries)
        elif report_format == ReportFormat.PDF:
            content = self._build_pdf(application, audit_entries)
        else:  # pragma: no cover - guarded by the ReportFormat enum/pydantic validation
            raise ValueError(f"Unsupported report format: {report_format}")

        media_type = MEDIA_TYPES[report_format]
        filename = f"application-{application.application_id}-report.{report_format.value}"
        return content, media_type, filename

    def _application_dict(self, application: Application) -> dict:
        return {
            "application_id": application.application_id,
            "applicant_id": application.applicant_id,
            "service_id": application.service_id,
            "status": application.status,
            "otp_verified": application.otp_verified,
            "submission_hash": application.submission_hash,
            "created_at": application.created_at.isoformat() if application.created_at else None,
            "submitted_at": application.submitted_at.isoformat() if application.submitted_at else None,
        }

    def _fields_rows(self, application: Application) -> list[dict]:
        return [
            {
                "field_name": f.field_name,
                "original_value": f.original_value,
                "current_value": f.current_value,
                "is_edited": f.is_edited,
                "confidence": f.confidence,
                "confidence_level": f.confidence_level,
                "source_document": f.source_document,
                "is_required": f.is_required,
                "decision_status": f.decision_status,
                "decision_note": f.decision_note,
                "decided_by": f.decided_by,
                "decided_at": f.decided_at.isoformat() if f.decided_at else None,
            }
            for f in application.fields
        ]

    def _build_csv(self, application: Application) -> bytes:
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        writer.writerow(["Application Report"])
        for key, value in self._application_dict(application).items():
            writer.writerow([key, value])
        writer.writerow([])

        writer.writerow(
            [
                "field_name",
                "original_value",
                "current_value",
                "is_edited",
                "confidence",
                "confidence_level",
                "source_document",
                "is_required",
                "decision_status",
                "decision_note",
                "decided_by",
                "decided_at",
            ]
        )
        for row in self._fields_rows(application):
            writer.writerow([row[key] for key in row])

        return buffer.getvalue().encode("utf-8")

    def _build_json(self, application: Application, audit_entries: list[AuditLogEntry]) -> bytes:
        payload = {
            "application": self._application_dict(application),
            "fields": self._fields_rows(application),
            "audit_log": [
                {
                    "sequence_number": entry.sequence_number,
                    "action": entry.action,
                    "field_name": entry.field_name,
                    "actor": entry.actor,
                    "details": json.loads(entry.details) if entry.details else {},
                    "entry_hash": entry.entry_hash,
                    "created_at": entry.created_at.isoformat() if entry.created_at else None,
                }
                for entry in audit_entries
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        return json.dumps(payload, indent=2, default=str).encode("utf-8")

    def _build_pdf(self, application: Application, audit_entries: list[AuditLogEntry]) -> bytes:
        from fpdf import FPDF  # imported lazily so CSV/JSON reports never require fpdf2 to be installed
        from fpdf.enums import XPos, YPos

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Sahaay.AI - Application Decision Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        pdf.ln(2)

        for key, value in self._application_dict(application).items():
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(45, 6, f"{key}:", border=0)
            pdf.set_font("Helvetica", "", 10)
            # new_x=LMARGIN, new_y=NEXT: return to the left margin on the
            # next line. multi_cell's own default (new_x=XPos.RIGHT) parks
            # the cursor at the right margin instead, which made every
            # following cell()/multi_cell() pair in this loop start further
            # right than the last, eventually running off the page and
            # raising "Not enough horizontal space to render a single
            # character".
            pdf.multi_cell(0, 6, "" if value is None else str(value), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Fields", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9)

        for row in self._fields_rows(application):
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, row["field_name"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(
                0,
                5,
                f"  Value: {row['current_value']} (original: {row['original_value']}, "
                f"edited: {row['is_edited']})\n"
                f"  Confidence: {row['confidence']} ({row['confidence_level']}) "
                f"from {row['source_document']}\n"
                f"  Required: {row['is_required']} | Status: {row['decision_status']}\n"
                f"  Decided by: {row['decided_by']} at {row['decided_at']}"
                + (f"\n  Note: {row['decision_note']}" if row["decision_note"] else ""),
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
            pdf.ln(1)

        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Audit Trail", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8)

        for entry in audit_entries:
            details = json.loads(entry.details) if entry.details else {}
            line = (
                f"#{entry.sequence_number} [{entry.created_at}] {entry.action} "
                f"by {entry.actor}"
                + (f" (field: {entry.field_name})" if entry.field_name else "")
            )
            pdf.multi_cell(0, 4.5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            if details:
                pdf.set_text_color(90, 90, 90)
                pdf.multi_cell(
                    0, 4.5, f"    {json.dumps(details, default=str)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT
                )
                pdf.set_text_color(0, 0, 0)

        return bytes(pdf.output())
