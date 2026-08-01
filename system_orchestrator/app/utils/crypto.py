import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from .hashing import sha256_text


def derive_key(secret: str) -> bytes:
    if not secret:
        raise ValueError("Encryption key is required")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_text(secret: str, text: str) -> str:
    key = derive_key(secret)
    f = Fernet(key)
    return f.encrypt(text.encode("utf-8")).decode("utf-8")


def decrypt_text(secret: str, token: str) -> str:
    key = derive_key(secret)
    f = Fernet(key)
    try:
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Invalid encrypted payload") from exc


def compute_document_hash(text: str) -> str:
    return sha256_text(text)
