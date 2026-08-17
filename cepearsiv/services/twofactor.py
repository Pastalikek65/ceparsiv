import hashlib
import io
import secrets
from datetime import datetime, timezone

import pyotp
from sqlmodel import Session, select

from cepearsiv.models import BackupCode, User

BACKUP_CODE_COUNT = 10


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()


def generate_backup_codes(session: Session, user_id: int) -> list[str]:
    codes: list[str] = []
    for _ in range(BACKUP_CODE_COUNT):
        plain = f"{secrets.token_hex(2)}-{secrets.token_hex(2)}".upper()
        codes.append(plain)
        session.add(BackupCode(user_id=user_id, code_hash=hash_code(plain)))
    session.commit()
    return codes


def verify_backup_code(session: Session, user_id: int, code: str) -> bool:
    row = session.exec(
        select(BackupCode).where(
            BackupCode.user_id == user_id,
            BackupCode.code_hash == hash_code(code),
            BackupCode.used_at == None,  # noqa: E711
        )
    ).first()
    if row is None:
        return False
    row.used_at = _utcnow()
    session.add(row)
    session.commit()
    return True


def clear_backup_codes(session: Session, user_id: int) -> None:
    rows = session.exec(select(BackupCode).where(BackupCode.user_id == user_id)).all()
    for row in rows:
        session.delete(row)
    session.commit()


def verify_totp(secret: str, code: str) -> bool:
    try:
        return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
    except Exception:
        return False


def verify_login_code(session: Session, user_id: int, code: str) -> bool:
    user = session.get(User, user_id)
    if user is None or not user.otp_enabled or user.otp_secret is None:
        return False
    if verify_totp(user.otp_secret, code):
        return True
    return verify_backup_code(session, user_id, code)


def provisioning_svg(secret: str, username: str) -> str:
    import qrcode
    from qrcode.image.svg import SvgImage

    uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="CepArsiv")
    image = qrcode.make(uri, image_factory=SvgImage)
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue().decode()
