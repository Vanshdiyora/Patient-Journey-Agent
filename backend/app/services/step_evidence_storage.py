from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.core.config import settings

MAX_EVIDENCE_FILE_BYTES = 1024 * 1024
ALLOWED_EVIDENCE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".docx"}


class EvidenceFileError(ValueError):
    pass


def save_evidence_file(upload: UploadFile) -> tuple[UUID, str, int]:
    original_name = Path((upload.filename or "").replace("\\", "/")).name
    original_name = "".join(character for character in original_name if character.isprintable()).strip()
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EVIDENCE_EXTENSIONS:
        raise EvidenceFileError("Upload a PDF, PNG, JPG, TXT, or DOCX file.")

    file_id = uuid4()
    storage_dir = settings.evidence_storage_dir.resolve()
    storage_dir.mkdir(parents=True, exist_ok=True)
    destination = storage_dir / file_id.hex
    total_bytes = 0

    try:
        with destination.open("xb") as target:
            while chunk := upload.file.read(64 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_EVIDENCE_FILE_BYTES:
                    raise EvidenceFileError("Evidence files must be 1 MB or smaller.")
                target.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    if total_bytes == 0:
        destination.unlink(missing_ok=True)
        raise EvidenceFileError("The selected file is empty.")

    return file_id, original_name, total_bytes


def evidence_file_path(file_id: UUID) -> Path:
    return settings.evidence_storage_dir.resolve() / file_id.hex
