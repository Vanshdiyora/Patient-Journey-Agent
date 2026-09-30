"""
Sync the users table from the canonical seed JSON
(files/Database creation/patient_journey_users.json).

- Matches rows by entra_object_id (deterministic across seed formats).
- Updates email, display_name, role, is_active for existing rows.
- Inserts rows that are missing.
- Never deletes: users absent from the JSON are left untouched.

Usage:
    python scripts/sync_users_from_json.py [path/to/patient_journey_users.json]
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.models.user import User

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_JSON = BACKEND_DIR.parents[1] / "files" / "Database creation" / "patient_journey_users.json"


def main() -> None:
    json_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_JSON
    if not json_path.exists():
        print(f"JSON file not found: {json_path}")
        sys.exit(1)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    users = payload.get("users", [])
    print(f"Loaded {len(users)} users from {json_path.name}")

    db = SessionLocal()
    now = datetime.now(timezone.utc)
    updated = inserted = unchanged = 0

    try:
        for entry in users:
            user = db.query(User).filter(User.entra_object_id == entry["entra_object_id"]).first()
            if user:
                changed = (
                    user.email != entry["email"]
                    or user.display_name != entry["display_name"]
                    or user.role != entry["role"]
                    or user.is_active != entry["is_active"]
                )
                if changed:
                    user.email = entry["email"]
                    user.display_name = entry["display_name"]
                    user.role = entry["role"]
                    user.is_active = entry["is_active"]
                    user.updated_at = now
                    updated += 1
                else:
                    unchanged += 1
            else:
                db.add(User(
                    id=entry["id"],
                    entra_object_id=entry["entra_object_id"],
                    email=entry["email"],
                    display_name=entry["display_name"],
                    role=entry["role"],
                    is_active=entry["is_active"],
                    created_at=entry.get("created_at", now),
                    updated_at=entry.get("updated_at", now),
                ))
                inserted += 1
        db.commit()
        print(f"Done: {inserted} inserted, {updated} updated, {unchanged} unchanged.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
