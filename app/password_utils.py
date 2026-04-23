from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets

try:
    from passlib.context import CryptContext as PasslibCryptContext
except ModuleNotFoundError:  # pragma: no cover - depends on runtime env
    PasslibCryptContext = None

_log = logging.getLogger(__name__)

PBKDF2_SCHEME = 'pbkdf2-sha256'
PBKDF2_ROUNDS = 29000
PBKDF2_SALT_BYTES = 16


def _ab64_encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode('ascii').rstrip('=').replace('+', '.')


def _ab64_decode(value: str) -> bytes:
    normalized = value.replace('.', '+')
    padding = '=' * (-len(normalized) % 4)
    return base64.b64decode(normalized + padding)


class FallbackPasswordContext:
    """Compatibility fallback for passlib pbkdf2_sha256 hashes."""

    def __init__(self, rounds: int = PBKDF2_ROUNDS):
        self.rounds = rounds

    def hash(self, password: str) -> str:
        salt = secrets.token_bytes(PBKDF2_SALT_BYTES)
        checksum = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            self.rounds,
        )
        return f'${PBKDF2_SCHEME}${self.rounds}${_ab64_encode(salt)}${_ab64_encode(checksum)}'

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            _, scheme, rounds_text, salt_text, checksum_text = str(password_hash or '').split('$')
            if scheme != PBKDF2_SCHEME:
                return False
            salt = _ab64_decode(salt_text)
            expected = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt,
                int(rounds_text),
            )
            actual = _ab64_decode(checksum_text)
            return hmac.compare_digest(expected, actual)
        except Exception:
            return False


def build_password_context():
    if PasslibCryptContext is not None:
        return PasslibCryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')

    _log.warning('passlib 未安装，已切换到内置 pbkdf2_sha256 兼容实现')
    return FallbackPasswordContext()


pwd_context = build_password_context()
