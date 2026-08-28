import os
import httpx
from fastapi import Request, HTTPException

# URL interna do auth-service obtida das variáveis de ambiente
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001").rstrip("/")


async def login_user(email: str, senha: str) -> dict:
    """Repassa as credenciais para o auth-service e obtém o token JWT e dados do usuário."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{AUTH_SERVICE_URL}/auth/login",
                json={"email": email, "senha": senha},
            )
            if resp.status_code == 200:
                return {"success": True, "data": resp.json()}
            detail = resp.json().get("detail", "Erro ao realizar login.")
            return {"success": False, "error": detail}
        except httpx.RequestError as e:
            return {"success": False, "error": f"Serviço de autenticação indisponível: {e}"}


async def register_user(nome: str, email: str, senha: str, role: str = "user") -> dict:
    """Repassa o registro de novo usuário para o auth-service."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{AUTH_SERVICE_URL}/auth/register",
                json={"nome": nome, "email": email, "senha": senha, "role": role},
            )
            if resp.status_code in (200, 201):
                return {"success": True, "data": resp.json()}
            detail = resp.json().get("detail", "Erro ao criar conta.")
            return {"success": False, "error": detail}
        except httpx.RequestError as e:
            return {"success": False, "error": f"Serviço de autenticação indisponível: {e}"}


async def verify_token(token: str) -> dict | None:
    """Valida o token JWT junto ao auth-service."""
    if not token:
        return None
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{AUTH_SERVICE_URL}/auth/verify",
                json={"token": token},
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except httpx.RequestError:
            return None


async def get_current_user(request: Request) -> dict:
    """
    Extrai o token dos cookies e valida a sessão no auth-service.
    Lança HTTPException 401 caso não esteja autenticado.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")

    user = await verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada")

    return user


async def request_password_reset(email: str, base_url: str | None = None) -> dict:
    """Solicita o disparo de e-mail de recuperação de senha ao auth-service."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{AUTH_SERVICE_URL}/auth/forgot-password",
                json={"email": email, "base_url": base_url},
            )
            if resp.status_code == 200:
                return {"success": True, "data": resp.json()}
            detail = resp.json().get("detail", "Erro ao solicitar recuperação.")
            return {"success": False, "error": detail}
        except httpx.RequestError as e:
            return {"success": False, "error": f"Serviço de autenticação indisponível: {e}"}


async def validate_reset_token(token: str) -> dict:
    """Consulta o auth-service para verificar se o token de reset é válido e não expirou."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{AUTH_SERVICE_URL}/auth/reset-password/validate",
                params={"token": token},
            )
            if resp.status_code == 200:
                return {"valid": True, "data": resp.json()}
            detail = resp.json().get("detail", "Token inválido ou expirado.")
            return {"valid": False, "error": detail}
        except httpx.RequestError as e:
            return {"valid": False, "error": f"Serviço de autenticação indisponível: {e}"}


async def reset_password(token: str, nova_senha: str) -> dict:
    """Envia o token e nova senha para efetivação no auth-service."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{AUTH_SERVICE_URL}/auth/reset-password",
                json={"token": token, "nova_senha": nova_senha},
            )
            if resp.status_code == 200:
                return {"success": True, "data": resp.json()}
            detail = resp.json().get("detail", "Erro ao redefinir senha.")
            return {"success": False, "error": detail}
        except httpx.RequestError as e:
            return {"success": False, "error": f"Serviço de autenticação indisponível: {e}"}

