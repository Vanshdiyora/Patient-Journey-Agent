import re
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PathwayStepCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    step_type: str = Field(min_length=1, max_length=50)
    time_limit_hours: int = Field(ge=1, le=8760)
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
