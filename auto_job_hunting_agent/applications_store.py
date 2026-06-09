from __future__ import annotations

import json
from pathlib import Path

from auto_job_hunting_agent.models import ApplicationRecord, ApplicationStatus

_STORE = Path(__file__).resolve().parent.parent / ".data" / "applications.json"


def _ensure_dir() -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)


def load_applications() -> list[ApplicationRecord]:
    _ensure_dir()
    if not _STORE.exists():
        return []
    try:
        raw = json.loads(_STORE.read_text(encoding="utf-8"))
        return [ApplicationRecord.model_validate(x) for x in raw]
    except (json.JSONDecodeError, OSError):
        return []


def save_applications(records: list[ApplicationRecord]) -> None:
    _ensure_dir()
    payload = [r.model_dump() for r in records]
    _STORE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def add_application(record: ApplicationRecord) -> list[ApplicationRecord]:
    records = load_applications()
    records = [r for r in records if r.job_id != record.job_id]
    records.insert(0, record)
    save_applications(records)
    return records


def update_status(app_id: str, status: ApplicationStatus) -> list[ApplicationRecord]:
    records = load_applications()
    for r in records:
        if r.id == app_id:
            r.status = status
    save_applications(records)
    return records
