"""Narrow, deterministic checks at the chat model's untrusted text boundaries.

These checks catch recognizable instruction override attempts. They are not an
authorization mechanism: tool permissions and patient scope remain server-side.
"""

import re
import unicodedata
import hashlib
import hmac
import json
from typing import Any

from app.core.config import settings


_OVERRIDE_PATTERNS = (
    re.compile(r"\b(?:ignore|disregard|forget|override)\s+(?:(?:all|any|the)\s+)?(?:previous|prior|above|system|developer)\s+(?:instructions?|rules?|prompts?|messages?)\b", re.I),
    re.compile(r"\b(?:reveal|print|show|dump|repeat|expose)\s+(?:(?:the|your|full|hidden|secret)\s+)*(?:system|developer)\s+(?:prompt|message|instructions?)\b", re.I),
    re.compile(r"\b(?:reveal|print|show|dump|repeat|expose)\s+(?:(?:me|us|the|your|all)\s+)*(?:hidden|internal|secret)\s+(?:(?:system|developer)\s+)?(?:instructions?|prompts?|rules?|messages?)\b", re.I),
    re.compile(r"\b(?:you are now|act as|pretend (?:you are|to be))\s+(?:an?\s+|the\s+)?(?:system|developer|administrator|admin)\b", re.I),
    re.compile(r"(?:\[im_start\]|<\|im_start\|>|\[start_header_id\]|<\|start_header_id\|>)\s*(?:system|developer|assistant|tool)\b", re.I),
    re.compile(r"(?:^|\n)\s*(?:#{1,6}\s*)?(?:system|developer)\s*(?:message|instructions?|prompt)?\s*:", re.I),
    re.compile(r"\b(?:i am|i'm)\s+(?:the\s+)?(?:admin|administrator)\b.{0,100}\b(?:bypass|override|ignore)\b", re.I | re.S),
    re.compile(r"\b(?:bypass|skip|disable)\s+(?:authorization|permissions?|confirmation)\b", re.I),
    re.compile(r"\b(?:call|invoke|use)\s+(?:this|the|an?)\s+api\b.{0,100}\b(?:without|skip|bypass)\s+confirmation\b", re.I | re.S),
)


def contains_instruction_override(value: str) -> bool:
    """Detect explicit role spoofing or requests to replace/reveal instructions."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", normalized)
    return any(pattern.search(normalized) for pattern in _OVERRIDE_PATTERNS)


def redact_tool_instructions(value: Any) -> tuple[Any, bool]:
    """Keep retrieved text as data while removing recognizable embedded orders."""
    if isinstance(value, str):
        if contains_instruction_override(value):
            return "[Untrusted instruction removed]", True
        return value, False
    if isinstance(value, list):
        items = [redact_tool_instructions(item) for item in value]
        return [item for item, _ in items], any(changed for _, changed in items)
    if isinstance(value, dict):
        items = {key: redact_tool_instructions(item) for key, item in value.items()}
        return {key: item for key, (item, _) in items.items()}, any(changed for _, changed in items.values())
    return value, False


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def parameter_fingerprint(arguments: Any) -> str:
    return hashlib.sha256(canonical_json(arguments).encode("utf-8")).hexdigest()


def sign_pending_action(pending: dict[str, Any], user_id: Any, session_id: Any) -> str:
    """Bind the proposal, including its description and exact arguments, to its owner."""
    payload = {key: value for key, value in pending.items() if key != "binding"}
    raw = canonical_json({"user_id": str(user_id), "session_id": str(session_id), "pending": payload})
    return hmac.new(settings.auth_jwt_secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_pending_action(pending: dict[str, Any], user_id: Any, session_id: Any) -> bool:
    supplied = pending.get("binding")
    return isinstance(supplied, str) and hmac.compare_digest(
        supplied, sign_pending_action(pending, user_id, session_id)
    )
