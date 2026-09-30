"""
Microsserviço de Logs e Auditoria (log-service)
Responsável exclusivamente por:
- Receber eventos de auditoria dos demais serviços via HTTP interno.
- Persistir os eventos em Redis Streams (XADD).
- Expor consulta de logs protegida por RBAC (somente admin).
"""

import os
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis
from fastapi import FastAPI, HTTPException, status, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from jose import JWTError, jwt


# ── Configuração ────────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
SECRET_KEY = os.getenv("SECRET_KEY", "secret-key-change-in-production")
ALGORITHM = "HS256"
STREAM_KEY = "log:eventos"


# ── Conexão Redis ───────────────────────────────────────
redis_client: redis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
        )
        redis_client.ping()
        print(f"[LogService] Conectado ao Redis em {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        print(f"[LogService] Aviso: não foi possível conectar ao Redis: {e}")
        redis_client = None
    yield
    if redis_client:
        redis_client.close()


app = FastAPI(
    title="Log Service — Microsserviço de Auditoria",
    description="Serviço privado de logs e auditoria centralizada com Redis Streams.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Modelos ─────────────────────────────────────────────
class LogEvent(BaseModel):
    usuario_id: int
    acao: str
    timestamp: str | None = None
    detalhe: str | None = None
    ip_origem: str | None = None


# ── Helpers de Autenticação ─────────────────────────────
def _decode_token(token: str) -> dict | None:
    """Decodifica o JWT localmente usando a SECRET_KEY compartilhada."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def _extract_token(authorization: str | None = None) -> str | None:
    """Extrai o token Bearer do header Authorization."""
    if authorization and authorization.startswith("Bearer "):
        return authorization.split("Bearer ")[1].strip()
    return None


# ── Endpoints ───────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check do serviço de logs."""
    redis_ok = False
    if redis_client:
        try:
            redis_ok = redis_client.ping()
        except Exception:
            pass
    return {"status": "ok", "service": "log-service", "redis": redis_ok}


@app.post("/logs", status_code=status.HTTP_201_CREATED)
async def create_log(event: LogEvent):
    """
    Recebe um evento de auditoria e persiste no Redis Stream via XADD.
    Chamado internamente pelos demais serviços (catalog-service, auth-service).
    """
    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis indisponível.",
        )

    # Preencher timestamp se não fornecido
    timestamp = event.timestamp or datetime.now(timezone.utc).isoformat()

    # Serializar o evento como JSON para armazenar no campo 'data' do Stream
    evento_data = {
        "usuario_id": str(event.usuario_id),
        "acao": event.acao,
        "timestamp": timestamp,
        "detalhe": event.detalhe or "",
        "ip_origem": event.ip_origem or "",
    }

    try:
        entry_id = redis_client.xadd(STREAM_KEY, {"data": json.dumps(evento_data)})
        return {"status": "ok", "stream_id": entry_id}
    except Exception as e:
        print(f"[LogService] Erro ao gravar evento no Redis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao gravar evento de log.",
        )


@app.get("/logs")
async def get_logs(
    limit: int = Query(default=50, ge=1, le=500),
    authorization: Optional[str] = Header(None),
):
    """
    Retorna os últimos N eventos de auditoria do Redis Stream.
    Protegida por RBAC: somente admin (role == 'admin') pode acessar.
    """
    # ── Autenticação e Autorização ──
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso não fornecido.",
        )

    payload = _decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
        )

    if payload.get("role", "user") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: somente administradores.",
        )

    # ── Consulta Redis Stream ──
    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis indisponível.",
        )

    try:
        # XREVRANGE retorna os mais recentes primeiro
        entries = redis_client.xrevrange(STREAM_KEY, count=limit)
        logs = []
        for entry_id, fields in entries:
            try:
                data = json.loads(fields.get("data", "{}"))
                data["stream_id"] = entry_id
                logs.append(data)
            except json.JSONDecodeError:
                logs.append({"stream_id": entry_id, "raw": fields})
        return {"total": len(logs), "logs": logs}
    except Exception as e:
        print(f"[LogService] Erro ao ler eventos do Redis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao consultar logs.",
        )
