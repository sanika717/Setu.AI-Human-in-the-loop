import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import AuditLogEntry
from ..models.enums import AuditAction
from ..utils.hashing import GENESIS_HASH, canonical_json, compute_entry_hash


def _iso_utc(dt: datetime) -> str:
    """Deterministic ISO-8601 string for hashing, independent of whether
    `dt` still carries tzinfo. SQLite (via aiosqlite) silently drops tzinfo
    from DateTime(timezone=True) columns on read-back, so a value hashed
    right after creation (tz-aware) and the same value re-read from the DB
    later (naive) must still serialize identically, or every recomputed
    hash would mismatch its stored hash even though nothing was tampered
    with. All timestamps in this engine are generated with
    `datetime.now(timezone.utc)`, so naive values are always UTC already.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class AuditService:
    """Append-only audit trail with a hash chain for tamper-evidence.

    Entries are never updated or deleted by any code path in this engine —
    the service only exposes `record` (insert) and read methods. Each
    entry's hash is computed over its own content plus the previous entry's
    hash, so altering, deleting, or reordering any historical row breaks the
    chain from that point forward, which `verify_chain` detects.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _last_entry(self, application_pk: int) -> AuditLogEntry | None:
        result = await self.session.execute(
            select(AuditLogEntry)
            .where(AuditLogEntry.application_id == application_pk)
            .order_by(AuditLogEntry.sequence_number.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def record(
        self,
        application_pk: int,
        action: AuditAction,
        actor: str,
        field_name: str | None = None,
        details: dict | None = None,
    ) -> AuditLogEntry:
        details = details or {}
        last = await self._last_entry(application_pk)
        sequence_number = (last.sequence_number + 1) if last else 1
        previous_hash = last.entry_hash if last else GENESIS_HASH

        created_at = datetime.now(timezone.utc)
        hash_payload = {
            "application_id": application_pk,
            "sequence_number": sequence_number,
            "action": action.value,
            "field_name": field_name,
            "actor": actor,
            "details": details,
            "created_at": _iso_utc(created_at),
        }
        entry_hash = compute_entry_hash(hash_payload, previous_hash)

        entry = AuditLogEntry(
            application_id=application_pk,
            sequence_number=sequence_number,
            action=action.value,
            field_name=field_name,
            actor=actor,
            details=canonical_json(details),
            previous_hash=previous_hash,
            entry_hash=entry_hash,
            created_at=created_at,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def list_for_application(self, application_pk: int) -> list[AuditLogEntry]:
        result = await self.session.execute(
            select(AuditLogEntry)
            .where(AuditLogEntry.application_id == application_pk)
            .order_by(AuditLogEntry.sequence_number.asc())
        )
        return list(result.scalars().all())

    async def verify_chain(self, application_pk: int) -> tuple[bool, int | None, str]:
        """Recomputes every entry's hash from its stored content and compares
        it against what's stored, and checks previous_hash linkage. Returns
        (is_valid, first_broken_sequence_number_or_None, detail_message).
        """

        entries = await self.list_for_application(application_pk)
        if not entries:
            return True, None, "No audit entries yet."

        expected_previous = GENESIS_HASH
        for entry in entries:
            if entry.previous_hash != expected_previous:
                return (
                    False,
                    entry.sequence_number,
                    f"Entry {entry.sequence_number} has previous_hash that does not match "
                    f"entry {entry.sequence_number - 1}'s hash. Chain is broken.",
                )

            hash_payload = {
                "application_id": entry.application_id,
                "sequence_number": entry.sequence_number,
                "action": entry.action,
                "field_name": entry.field_name,
                "actor": entry.actor,
                "details": json.loads(entry.details) if entry.details else {},
                "created_at": _iso_utc(entry.created_at),
            }
            recomputed = compute_entry_hash(hash_payload, entry.previous_hash)
            if recomputed != entry.entry_hash:
                return (
                    False,
                    entry.sequence_number,
                    f"Entry {entry.sequence_number}'s stored hash does not match its recomputed "
                    "hash. Content has been tampered with.",
                )
            expected_previous = entry.entry_hash

        return True, None, f"All {len(entries)} audit entries verified intact."
