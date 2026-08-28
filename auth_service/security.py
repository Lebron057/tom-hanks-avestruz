import os
import secrets
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import JWTError, jwt

# ── Hashing de senha (Bcrypt) ───────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Gera hash seguro da senha com bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto confere com o hash armazenado."""
    return pwd_context.verify(plain_password, hashed_password)


# ── Tokens JWT para Sessão ──────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def create_access_token(usuario_id: int, nome: str, email: str, role: str = "user") -> str:
    """Gera um token JWT contendo os dados de sessão do usuário e papel."""
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(usuario_id),
        "nome": nome,
        "email": email,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decodifica e valida o token JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# ── Tokens de Recuperação de Senha ──────────────────────────────
def generate_reset_token() -> str:
    """Gera um token seguro de 32 bytes em formato URL-safe para reset de senha."""
    return secrets.token_urlsafe(32)
