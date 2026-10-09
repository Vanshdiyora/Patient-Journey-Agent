"""Search patient identity fields before applying any result pagination."""

from sqlalchemy import literal, or_

from app.models import Patient


def patient_search_condition(search: str):
    term = f"%{' '.join(search.split())}%"
    full_name = Patient.first_name + literal(" ") + Patient.last_name
    return or_(
        Patient.patient_reference.ilike(term),
        Patient.first_name.ilike(term),
        Patient.last_name.ilike(term),
        full_name.ilike(term),
    )
