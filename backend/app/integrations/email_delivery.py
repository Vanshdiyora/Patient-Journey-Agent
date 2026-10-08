"""
Real patient communication over SMTP.

Used by the action executor in place of the mock services whenever SMTP is
configured (see Settings.email_enabled). Each method returns the same shape as
the mock services ({"accepted", "status", "external_reference", ...}) so the
verification layer treats both identically; "delivery" tells them apart.
"""
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Patient


def _mask(address: str) -> str:
    name, _, domain = address.partition("@")
    return f"{name[:2]}***@{domain}" if domain else "***"


def send_email(to: str, subject: str, body: str) -> dict[str, Any]:
    if settings.smtp_timeout_seconds is None:
        raise RuntimeError("SMTP_TIMEOUT_SECONDS is not configured")
    recipient = settings.smtp_redirect_to or to
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message["Subject"] = ("[TEST] " if settings.smtp_redirect_to else "") + subject
    message["Message-ID"] = make_msgid()
    message.set_content(body if not settings.smtp_redirect_to else f"(Intended for {to})\n\n{body}")
    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        ) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # Only the exception type is reported - never server banners or credentials.
        return {"accepted": False, "status": "EMAIL_FAILED", "reason": f"Email could not be sent ({type(exc).__name__})."}
    return {
        "accepted": True, "status": "EMAIL_SENT", "delivery": "email",
        "external_reference": message["Message-ID"], "recipient": _mask(recipient),
    }


class EmailPatientService:
    """Patient-facing reminders and requests, sent to the patient's email on file."""

    def __init__(self, db: Session):
        self.db = db

    def _patient(self, payload: dict[str, Any]) -> Patient | None:
        try:
            return self.db.query(Patient).filter(Patient.id == UUID(str(payload.get("patient_id")))).first()
        except (TypeError, ValueError):
            return None

    def _send(self, payload: dict[str, Any], subject: str, lines: list[str]) -> dict[str, Any]:
        patient = self._patient(payload)
        if not patient:
            return {"accepted": False, "status": "NO_RECIPIENT", "reason": "The patient could not be found."}
        if not patient.email:
            return {"accepted": False, "status": "NO_RECIPIENT", "reason": "The patient has no email address on file."}
        body = "\n".join([f"Hello {patient.first_name},", "", *lines, "", "Kind regards,", "Your care team"])
        return send_email(patient.email, subject, body)

    @staticmethod
    def _step(payload: dict[str, Any]) -> str:
        return payload.get("step_name") or "your care plan"

    def send_reminder(self, payload):
        return self._send(payload, "A reminder from your care team", [
            f"This is a friendly reminder about: {self._step(payload)}.",
            "Please complete it or contact your care team if you need help.",
        ])

    def request_document(self, payload):
        return self._send(payload, "Document needed for your care", [
            f"We still need a document for: {self._step(payload)}.",
            "Please upload it in the patient portal or bring it to your next visit.",
        ])

    def request_appointment(self, payload):
        return self._send(payload, "Let's arrange your appointment", [
            f"Your care team is arranging an appointment for: {self._step(payload)}.",
            "Please reply with the days and times that suit you best.",
        ])

    def reschedule_appointment(self, payload):
        return self._send(payload, "Your appointment needs rescheduling", [
            f"Your appointment for {self._step(payload)} needs to be rescheduled.",
            "Please reply with new days and times that suit you.",
        ])
