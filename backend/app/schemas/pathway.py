import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

STEP_OWNER_ROLES = {"PATIENT", "CLINICIAN", "CARE_COORDINATOR", "ADMIN", "AGENT"}


class PathwayStepCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    step_type: str = Field(min_length=1, max_length=50)
    owner_role: str = "CARE_COORDINATOR"
    time_limit_hours: int = Field(ge=1, le=8760)
    due_after_days: int | None = Field(default=None, ge=0, le=365)
    completion_criteria: dict[str, Any] | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]*", value):
            raise ValueError("Step code may contain only letters, numbers, underscores, and hyphens")
        return value

    @field_validator("name", "step_type")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value

    @field_validator("owner_role")
    @classmethod
    def validate_owner_role(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in STEP_OWNER_ROLES:
            raise ValueError(f"Owner role must be one of: {', '.join(sorted(STEP_OWNER_ROLES))}")
        return normalized


class PathwayCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    steps: list[PathwayStepCreate] = Field(min_length=1, max_length=100)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]*", value):
            raise ValueError("Pathway code may contain only letters, numbers, underscores, and hyphens")
        return value

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Pathway name cannot be blank")
        return value

    @field_validator("steps")
    @classmethod
    def unique_step_codes(cls, steps: list[PathwayStepCreate]) -> list[PathwayStepCreate]:
        codes = [step.code for step in steps]
        if len(codes) != len(set(codes)):
            raise ValueError("Step codes must be unique within a pathway")
        return steps


class PathwayStepUpdate(PathwayStepCreate):
    id: UUID | None = None
    required: bool = True


class PathwayUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    steps: list[PathwayStepUpdate] = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Pathway name cannot be blank")
        return value

    @field_validator("steps")
    @classmethod
    def unique_steps(cls, steps: list[PathwayStepUpdate]) -> list[PathwayStepUpdate]:
        codes = [step.code for step in steps]
        ids = [step.id for step in steps if step.id is not None]
        if len(codes) != len(set(codes)):
            raise ValueError("Step codes must be unique within a pathway")
        if len(ids) != len(set(ids)):
            raise ValueError("A step cannot be included more than once")
        return steps
