import hashlib
import hmac
import json
import secrets

GENESIS_HASH = "0" * 64


def canonical_json(payload: dict) -> str:
    """Deterministic JSON serialization used for hashing.

    Sorted keys + fixed separators so the same logical payload always
    produces the same bytes, regardless of dict insertion order.
    """

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def compute_entry_hash(payload: dict, previous_hash: str) -> str:
    """Hash used to chain audit log entries together (tamper-evidence).

    Every entry's hash depends on its own content AND the previous entry's
    hash, so altering or deleting any historical entry breaks the chain from
    that point forward — detectable via AuditService.verify_chain().
    """

    body = dict(payload)
    body["previous_hash"] = previous_hash
    return sha256_hex(canonical_json(body))


def generate_numeric_code(length: int) -> str:
    """Cryptographically-secure random numeric code, e.g. a 6-digit OTP."""

    if length <= 0:
        raise ValueError("length must be positive")
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def generate_salt(num_bytes: int = 16) -> str:
    return secrets.token_hex(num_bytes)


def hash_otp_code(code: str, salt: str, pepper: str) -> str:
    """PBKDF2-HMAC-SHA256 hash of an OTP code with a per-challenge salt plus
    a deployment-wide pepper. Deliberately slow (100k iterations) to resist
    brute forcing of the (small, numeric) OTP space if the DB is ever leaked.
    """

    derived = hashlib.pbkdf2_hmac(
        "sha256",
        (code + pepper).encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    )
    return derived.hex()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
