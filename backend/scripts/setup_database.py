"""Create and seed an empty PostgreSQL/Neon database from backend/.env."""
import argparse
import os
import re
from pathlib import Path

import psycopg2
from psycopg2 import sql
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
TABLES = (
    "patients", "users", "pathways", "pathway_steps", "dependencies",
    "pathway_action_rules", "journeys", "journey_steps", "patient_events",
    "action_executions", "exceptions", "agent_runs", "chat_sessions",
    "chat_messages", "chat_audit_log",
)


def read_sql(path):
    # The connection owns the transaction, including the legacy seed script.
    return re.sub(r"^\s*(BEGIN|COMMIT);\s*$", "", path.read_text(encoding="utf-8"), flags=re.M)


def verify(cursor):
    counts = {}
    for table in TABLES:
        cursor.execute(sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(table)))
        counts[table] = cursor.fetchone()[0]
    empty = [table for table, count in counts.items() if count == 0]
    if empty:
        raise RuntimeError("Seed verification failed; empty tables: " + ", ".join(empty))
    cursor.execute("""
        SELECT count(*) FROM patients p LEFT JOIN users u ON u.patient_id = p.id
        AND u.role = 'PATIENT' WHERE u.id IS NULL
    """)
    if cursor.fetchone()[0]:
        raise RuntimeError("Seed verification failed: patients without portal accounts")
    cursor.execute("""
        SELECT count(*) FROM journey_steps js JOIN pathway_steps ps ON ps.id = js.pathway_step_id
        WHERE js.time_limit_hours IS NULL OR ps.time_limit_hours IS NULL
    """)
    if cursor.fetchone()[0]:
        raise RuntimeError("Seed verification failed: missing step time limits")
    cursor.execute("SELECT to_regclass('public.staff_patient_assignments')")
    if cursor.fetchone()[0] is None:
        raise RuntimeError("Staff patient assignment migration is missing")
    cursor.execute("""
        SELECT count(*) FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'journey_steps'
        AND column_name IN ('scheduled_start_at', 'scheduled_end_at', 'scheduled_staff_id', 'schedule_status', 'schedule_revision')
    """)
    if cursor.fetchone()[0] != 5:
        raise RuntimeError("Journey calendar migration is missing")
    cursor.execute("SELECT count(*) FROM pathway_steps WHERE owner_role = 'STAFF'")
    if cursor.fetchone()[0]:
        raise RuntimeError("Seed verification failed: generic pathway owner roles remain")
    cursor.execute("SELECT count(*) FROM patients WHERE patient_reference ~ '^PT-2026-[0-9]{6}$' AND assigned_clinician_id IS NULL")
    if cursor.fetchone()[0]:
        raise RuntimeError("Seed verification failed: demo patients lack clinicians")
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Check seeded tables without modifying data")
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL") or dotenv_values(ROOT / "backend" / ".env").get("DATABASE_URL")
    if not url:
        parser.error("Set DATABASE_URL in backend/.env first.")
    timeout_value = os.environ.get("DATABASE_CONNECT_TIMEOUT_SECONDS") or dotenv_values(
        ROOT / "backend" / ".env"
    ).get("DATABASE_CONNECT_TIMEOUT_SECONDS")
    try:
        connect_timeout = int(timeout_value)
    except (TypeError, ValueError):
        parser.error("Set DATABASE_CONNECT_TIMEOUT_SECONDS to a positive number of seconds.")
    if connect_timeout <= 0:
        parser.error("DATABASE_CONNECT_TIMEOUT_SECONDS must be a positive number of seconds.")
    url = re.sub(r"^postgresql\+psycopg2://", "postgresql://", url)
    if not url.startswith(("postgresql://", "postgres://")):
        parser.error("DATABASE_URL must be a PostgreSQL connection URL.")
    try:
        with psycopg2.connect(url, connect_timeout=connect_timeout) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO public")
                if not args.verify_only:
                    cursor.execute("SELECT pg_advisory_xact_lock(721046102)")
                    for table in TABLES:
                        cursor.execute("SELECT to_regclass(%s)", ("public." + table,))
                        if cursor.fetchone()[0]:
                            cursor.execute(sql.SQL("SELECT EXISTS (SELECT 1 FROM public.{} LIMIT 1)").format(sql.Identifier(table)))
                            if cursor.fetchone()[0]:
                                raise RuntimeError("Database already contains application data. Use an empty database/Neon branch, or --verify-only to check it. No data was changed.")
                    print("Creating schema...", flush=True)
                    schema = read_sql(ROOT / "db" / "Create Tables.sql")
                    schema = re.sub(r"CREATE TABLE (?!IF NOT EXISTS)", "CREATE TABLE IF NOT EXISTS ", schema)
                    schema = re.sub(r"CREATE INDEX (?!IF NOT EXISTS)", "CREATE INDEX IF NOT EXISTS ", schema)
                    cursor.execute(schema)
                    print("Seeding core tables (2,400 bcrypt hashes can take several minutes)...", flush=True)
                    seed = read_sql(ROOT / "db" / "patient_journey_orchestrator_seed.sql")
                    # Initialization never needs the legacy destructive reset section.
                    seed = re.sub(r"^DELETE FROM \w+;\s*$", "", seed, flags=re.M)
                    cursor.execute(seed)
                    for migration in sorted((ROOT / "backend" / "migrations").glob("*.sql")):
                        print("Applying " + migration.name, flush=True)
                        cursor.execute(read_sql(migration))
                    print("Applying clinical demo assignments and timeline dates...", flush=True)
                    cursor.execute(read_sql(ROOT / "db" / "clinical_seed_updates.sql"))
                    cursor.execute(read_sql(ROOT / "db" / "clinical_timeline_schedule.sql"))
                    print("Seeding chat conversations and audit records...", flush=True)
                    cursor.execute(read_sql(ROOT / "db" / "chat_seed.sql"))
                counts = verify(cursor)
        print("Verification passed." if args.verify_only else "Database setup committed successfully.")
        for table, count in counts.items():
            print(f"  {table}: {count:,}")
        print("Demo login password: Test@123")
    except psycopg2.Error as error:
        # Server primary errors avoid echoing credentials from connection strings.
        reason = error.diag.message_primary or "Connection/database operation failed; check DATABASE_URL and network access."
        print("Setup failed; transaction rolled back. " + reason)
        return 1
    except RuntimeError as error:
        print(str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
