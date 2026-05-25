from __future__ import annotations

import secrets

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("$"):
        return pwd_context.verify(password, stored_hash)
    return secrets.compare_digest(password, stored_hash)
