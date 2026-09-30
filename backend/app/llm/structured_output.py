from typing import Any, TypeVar, Type
from pydantic import BaseModel
T = TypeVar("T", bound=BaseModel)

def validate_structured_output(model: Type[T], data: dict[str, Any]) -> T:
    return model.model_validate(data)
