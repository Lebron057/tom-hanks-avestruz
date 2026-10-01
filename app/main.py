"""
Catálogo de Filmes — Tom Hanks (Catalog Service)
Ponto de entrada público da aplicação.
Responsabilidades:
- Interface do usuário (Jinja2 SSR) e arquivos estáticos.
- Integração com a API do TMDB para catálogo ao vivo de filmes.
- Persistência e segregação de favoritos e comentários por usuário no MariaDB.
- Delegação de autenticação, papéis e recuperação de senha ao auth-service privado.
- Disparo de eventos de auditoria para o log-service (Atividade 5).
- Rota de consulta de logs para administradores (/admin/logs).
- Perfil de usuário com upload de foto via MinIO (Atividade 6).
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import init_db, get_connection
from app.auth import (
    login_user,
    register_user,
    get_current_user,
    request_password_reset,
    validate_reset_token,
    reset_password,
)
from app.tmdb import get_tom_hanks_movies, get_movie_details
from app.minio_client import ensure_bucket, upload_avatar, delete_avatar, stream_avatar, MINIO_BUCKET
from minio.error import S3Error

# ── Configuração do MinIO ────────────────────────────────
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
# Tamanho máximo de upload: 3 MB
MAX_UPLOAD_BYTES = 3 * 1024 * 1024
# MIME types permitidos para foto de perfil
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


# ── Configuração do Log Service ─────────────────────────
LOG_SERVICE_URL = os.getenv("LOG_SERVICE_URL", "http://log-service:8002").rstrip("/")


# ── Lifespan ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: garante que as tabelas existam e o bucket MinIO esteja pronto
    try:
        init_db()
    except Exception as e:
        print(f"[CatalogService] Aviso ao inicializar banco: {e}")
    try:
        ensure_bucket()
    except Exception as e:
        print(f"[CatalogService] Aviso ao inicializar MinIO: {e}")
    yield


app = FastAPI(title="Catálogo Tom Hanks", lifespan=lifespan)

# Montar arquivos estáticos e templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# ── Helpers ─────────────────────────────────────────────
async def _get_user_or_none(request: Request) -> dict | None:
    """Tenta extrair o usuário do cookie e validar no auth-service."""
    try:
        return await get_current_user(request)
    except HTTPException:
        return None


async def _emit_log(
    usuario_id: int,
    acao: str,
    detalhe: str = "",
    ip_origem: str = "",
):
    """
    Dispara um evento de auditoria para o log-service via HTTP.
    Falhas são tratadas silenciosamente (try/except) para não
    derrubar a ação principal do usuário — log é 'best effort'.
    """
    try:
        payload = {
            "usuario_id": usuario_id,
            "acao": acao,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detalhe": detalhe,
            "ip_origem": ip_origem,
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{LOG_SERVICE_URL}/logs", json=payload)
    except Exception as e:
        print(f"[CatalogService] Falha ao enviar log (best-effort): {e}")


def _get_client_ip(request: Request) -> str:
    """Extrai o IP de origem da requisição."""
    if request.client:
        return request.client.host
    return ""


def _require_admin(user: dict):
    """
    Dependency reutilizável de RBAC: exige role == 'admin'.
    Levanta HTTPException(403) caso contrário.
    """
    if user.get("role", "user") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Acesso negado: somente administradores.",
        )


# ══════════════════════════════════════════════════════════
#  ROTAS PÚBLICAS & AUTENTICAÇÃO (Delegadas ao auth-service)
# ══════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "catalog-service"}


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = await _get_user_or_none(request)
    if user:
        return RedirectResponse(url="/catalog", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, success: str = None, error: str = None):
    user = await _get_user_or_none(request)
    if user:
        return RedirectResponse(url="/catalog", status_code=302)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "user": None,
        "error": error,
        "success": success,
    })


@app.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, email: str = Form(...), senha: str = Form(...)):
    result = await login_user(email=email, senha=senha)

    if not result.get("success"):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "user": None,
            "error": result.get("error", "E-mail ou senha incorretos."),
        })

    token_data = result["data"]
    token = token_data["access_token"]

    # ── Evento de auditoria: login bem-sucedido ──
    user_data = token_data.get("user", {})
    await _emit_log(
        usuario_id=user_data.get("id", 0),
        acao="login",
        detalhe=f"email={email}",
        ip_origem=_get_client_ip(request),
    )

    response = RedirectResponse(url="/catalog", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,  # 24 horas
    )
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = None):
    user = await _get_user_or_none(request)
    if user:
        return RedirectResponse(url="/catalog", status_code=302)
    return templates.TemplateResponse("register.html", {
        "request": request,
        "user": None,
        "error": error,
    })


@app.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
):
    if len(senha) < 6:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "user": None,
            "error": "A senha deve ter no mínimo 6 caracteres.",
        })

    result = await register_user(nome=nome, email=email, senha=senha, role="user")

    if not result.get("success"):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "user": None,
            "error": result.get("error", "Erro ao cadastrar usuário."),
        })

    return RedirectResponse(
        url="/login?success=Conta+criada+com+sucesso!+Faça+login.",
        status_code=302,
    )


@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request, error: str = None, success: str = None):
    user = await _get_user_or_none(request)
    if user:
        return RedirectResponse(url="/catalog", status_code=302)
    return templates.TemplateResponse("forgot-password.html", {
        "request": request,
        "user": None,
        "error": error,
        "success": success,
    })


@app.post("/forgot-password", response_class=HTMLResponse)
async def forgot_password_submit(request: Request, email: str = Form(...)):
    # Montar URL pública base para inclusão no e-mail
    base_url = str(request.base_url).rstrip("/")
    result = await request_password_reset(email=email, base_url=base_url)

    if not result.get("success"):
        return templates.TemplateResponse("forgot-password.html", {
            "request": request,
            "user": None,
            "error": result.get("error", "Erro ao processar recuperação de senha."),
        })

    return templates.TemplateResponse("forgot-password.html", {
        "request": request,
        "user": None,
        "success": "Se o e-mail estiver cadastrado, as instruções e o link de recuperação foram enviados via Mailtrap.",
    })


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = ""):
    if not token:
        return templates.TemplateResponse("reset-password.html", {
            "request": request,
            "user": None,
            "valid_token": False,
            "error": "Token de recuperação não fornecido.",
        })

    # Validação do token junto ao auth-service
    validation = await validate_reset_token(token)

    if not validation.get("valid"):
        return templates.TemplateResponse("reset-password.html", {
            "request": request,
            "user": None,
            "valid_token": False,
            "error": validation.get("error", "Token inválido ou expirado."),
        })

    user_info = validation.get("data", {})
    return templates.TemplateResponse("reset-password.html", {
        "request": request,
        "user": None,
        "valid_token": True,
        "token": token,
        "email": user_info.get("email", ""),
        "error": None,
    })


@app.post("/reset-password", response_class=HTMLResponse)
async def reset_password_submit(
    request: Request,
    token: str = Form(...),
    nova_senha: str = Form(...),
    confirmar_senha: str = Form(...),
):
    if nova_senha != confirmar_senha:
        return templates.TemplateResponse("reset-password.html", {
            "request": request,
            "user": None,
            "valid_token": True,
            "token": token,
            "error": "As senhas não coincidem.",
        })

    if len(nova_senha) < 6:
        return templates.TemplateResponse("reset-password.html", {
            "request": request,
            "user": None,
            "valid_token": True,
            "token": token,
            "error": "A senha deve ter no mínimo 6 caracteres.",
        })

    result = await reset_password(token=token, nova_senha=nova_senha)

    if not result.get("success"):
        return templates.TemplateResponse("reset-password.html", {
            "request": request,
            "user": None,
            "valid_token": True,
            "token": token,
            "error": result.get("error", "Erro ao redefinir senha."),
        })

    return RedirectResponse(
        url="/login?success=Senha+redefinida+com+sucesso!+Faça+login+com+sua+nova+senha.",
        status_code=302,
    )


@app.get("/logout")
async def logout(request: Request):
    # ── Evento de auditoria: logout ──
    user = await _get_user_or_none(request)
    if user:
        await _emit_log(
            usuario_id=user["id"],
            acao="logout",
            detalhe=f"email={user.get('email', '')}",
            ip_origem=_get_client_ip(request),
        )
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# ══════════════════════════════════════════════════════════
#  ROTAS PROTEGIDAS (CATÁLOGO, FAVORITOS E COMENTÁRIOS)
# ══════════════════════════════════════════════════════════

@app.get("/catalog", response_class=HTMLResponse)
async def catalog_page(request: Request, message: str = None):
    user = await _get_user_or_none(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Buscar filmes da TMDB em tempo real (sem persistência desnecessária no banco)
    try:
        movies = await get_tom_hanks_movies()
    except Exception as e:
        movies = []
        message = f"Erro ao buscar filmes da TMDB: {e}"

    # Buscar IDs dos filmes favoritados pelo usuário logado
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT tmdb_movie_id FROM favoritos WHERE usuario_id = %s",
            (user["id"],),
        )
        favorited_ids = {row["tmdb_movie_id"] for row in cursor.fetchall()}
    finally:
        cursor.close()
        conn.close()

    return templates.TemplateResponse("catalog.html", {
        "request": request,
        "user": user,
        "active_page": "catalog",
        "movies": movies,
        "favorited_ids": favorited_ids,
        "message": message,
        "error": None,
    })


@app.post("/favorite/{tmdb_movie_id}")
async def add_favorite(
    request: Request,
    tmdb_movie_id: int,
    titulo: str = Form(...),
    poster_path: str = Form(""),
):
    user = await _get_user_or_none(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT IGNORE INTO favoritos (usuario_id, tmdb_movie_id, titulo, poster_path)
               VALUES (%s, %s, %s, %s)""",
            (user["id"], tmdb_movie_id, titulo, poster_path or None),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    # ── Evento de auditoria: favoritar filme ──
    await _emit_log(
        usuario_id=user["id"],
        acao="favoritar",
        detalhe=f"tmdb_movie_id={tmdb_movie_id}, titulo={titulo}",
        ip_origem=_get_client_ip(request),
    )

    return RedirectResponse(url="/catalog?message=Filme+favoritado!", status_code=302)


@app.post("/favorite/{tmdb_movie_id}/remove")
async def remove_favorite(request: Request, tmdb_movie_id: int):
    user = await _get_user_or_none(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Proteção IDOR: sempre filtra por usuario_id do usuário logado
        cursor.execute(
            "DELETE FROM favoritos WHERE usuario_id = %s AND tmdb_movie_id = %s",
            (user["id"], tmdb_movie_id),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    referer = request.headers.get("referer", "/catalog")
    redirect_url = "/favorites?message=Favorito+removido!" if "favorites" in referer else "/catalog?message=Favorito+removido!"
    return RedirectResponse(url=redirect_url, status_code=302)


@app.post("/comment/{tmdb_movie_id}")
async def add_comment(
    request: Request,
    tmdb_movie_id: int,
    texto: str = Form(...),
    titulo: str = Form(""),
):
    user = await _get_user_or_none(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO comentarios (usuario_id, tmdb_movie_id, texto)
               VALUES (%s, %s, %s)""",
            (user["id"], tmdb_movie_id, texto),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    # ── Evento de auditoria: comentar ──
    await _emit_log(
        usuario_id=user["id"],
        acao="comentar",
        detalhe=f"tmdb_movie_id={tmdb_movie_id}, titulo={titulo}, texto={texto[:100]}",
        ip_origem=_get_client_ip(request),
    )

    referer = request.headers.get("referer", "/catalog")
    if f"/movie/{tmdb_movie_id}" in referer or "movie" in referer:
        redirect_url = f"/movie/{tmdb_movie_id}?message=Comentário+adicionado!"
    elif "favorites" in referer:
        redirect_url = "/favorites?message=Comentário+adicionado!"
    else:
        redirect_url = "/catalog?message=Comentário+adicionado!"
    return RedirectResponse(url=redirect_url, status_code=302)


@app.post("/comment/{comment_id}/remove")
async def remove_comment(request: Request, comment_id: int):
    user = await _get_user_or_none(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # RBAC: Buscar o comentário para verificar a quem pertence
        cursor.execute(
            "SELECT id, usuario_id FROM comentarios WHERE id = %s",
            (comment_id,),
        )
        comment = cursor.fetchone()

        if not comment:
            raise HTTPException(status_code=404, detail="Comentário não encontrado.")

        # Enforcement centralizado (Padrão A):
        # O role do usuário vem do auth-service (já validado via /auth/verify).
        # - admin: pode apagar QUALQUER comentário (moderação)
        # - user:  só pode apagar os PRÓPRIOS comentários
        is_owner = comment["usuario_id"] == user["id"]
        is_admin = user.get("role", "user") == "admin"

        if not is_owner and not is_admin:
            # ── Evento de auditoria: acesso negado (403) ──
            await _emit_log(
                usuario_id=user["id"],
                acao="acesso_negado_403",
                detalhe=f"tentativa de remover comentario_id={comment_id} de outro usuario",
                ip_origem=_get_client_ip(request),
            )
            raise HTTPException(
                status_code=403,
                detail="Acesso negado: você não tem permissão para apagar este comentário.",
            )

        # Determinar tipo de ação para o log
        if is_admin and not is_owner:
            acao_log = "remover_comentario_admin"
            detalhe_log = f"comentario_id={comment_id}, dono_id={comment['usuario_id']} (moderação)"
        else:
            acao_log = "remover_comentario_proprio"
            detalhe_log = f"comentario_id={comment_id}"

        cursor.execute("DELETE FROM comentarios WHERE id = %s", (comment_id,))
        conn.commit()

        # ── Evento de auditoria: remoção de comentário ──
        await _emit_log(
            usuario_id=user["id"],
            acao=acao_log,
            detalhe=detalhe_log,
            ip_origem=_get_client_ip(request),
        )
    finally:
        cursor.close()
        conn.close()

    referer = request.headers.get("referer", "/favorites")
    if "/movie/" in referer:
        # Extrair o movie_id do referer para redirecionar de volta à página de detalhes
        import re
        match = re.search(r"/movie/(\d+)", referer)
        if match:
            redirect_url = f"/movie/{match.group(1)}?message=Comentário+removido!"
        else:
            redirect_url = "/favorites?message=Comentário+removido!"
    elif "favorites" in referer:
        redirect_url = "/favorites?message=Comentário+removido!"
    else:
        redirect_url = "/catalog?message=Comentário+removido!"
    return RedirectResponse(url=redirect_url, status_code=302)


@app.get("/movie/{tmdb_movie_id}", response_class=HTMLResponse)
async def movie_detail_page(request: Request, tmdb_movie_id: int, message: str = None):
    """Página de detalhes do filme com seção de comentários e RBAC."""
    user = await _get_user_or_none(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Buscar detalhes do filme na TMDB
    try:
        movie = await get_movie_details(tmdb_movie_id)
    except Exception as e:
        movie = None

    if not movie:
        return templates.TemplateResponse("movie.html", {
            "request": request,
            "user": user,
            "active_page": "catalog",
            "movie": None,
            "comments": [],
            "is_favorited": False,
            "message": None,
            "error": "Filme não encontrado.",
        })

    # Verificar se o filme está favoritado pelo usuário
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id FROM favoritos WHERE usuario_id = %s AND tmdb_movie_id = %s",
            (user["id"], tmdb_movie_id),
        )
        is_favorited = cursor.fetchone() is not None

        # Buscar TODOS os comentários do filme (qualquer usuário), com nome do autor
        cursor.execute(
            """SELECT c.id, c.usuario_id, c.texto, c.criado_em, u.nome AS autor_nome
               FROM comentarios c
               JOIN usuarios u ON c.usuario_id = u.id
               WHERE c.tmdb_movie_id = %s
               ORDER BY c.criado_em DESC""",
            (tmdb_movie_id,),
        )
        comments = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return templates.TemplateResponse("movie.html", {
        "request": request,
        "user": user,
        "active_page": "catalog",
        "movie": movie,
        "comments": comments,
        "is_favorited": is_favorited,
        "message": message,
        "error": None,
    })


@app.get("/favorites", response_class=HTMLResponse)
async def favorites_page(request: Request, message: str = None):
    user = await _get_user_or_none(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Buscar favoritos do usuário logado (proteção IDOR)
        cursor.execute(
            """SELECT id, tmdb_movie_id, titulo, poster_path, criado_em
               FROM favoritos WHERE usuario_id = %s ORDER BY criado_em DESC""",
            (user["id"],),
        )
        favorites = cursor.fetchall()

        # Buscar comentários para cada filme favoritado
        # Admin vê TODOS os comentários (moderação); usuário comum vê apenas os próprios
        is_admin = user.get("role", "user") == "admin"
        for fav in favorites:
            if is_admin:
                cursor.execute(
                    """SELECT c.id, c.usuario_id, c.texto, c.criado_em, u.nome AS autor_nome
                       FROM comentarios c
                       JOIN usuarios u ON c.usuario_id = u.id
                       WHERE c.tmdb_movie_id = %s
                       ORDER BY c.criado_em ASC""",
                    (fav["tmdb_movie_id"],),
                )
            else:
                cursor.execute(
                    """SELECT c.id, c.usuario_id, c.texto, c.criado_em, u.nome AS autor_nome
                       FROM comentarios c
                       JOIN usuarios u ON c.usuario_id = u.id
                       WHERE c.usuario_id = %s AND c.tmdb_movie_id = %s
                       ORDER BY c.criado_em ASC""",
                    (user["id"], fav["tmdb_movie_id"]),
                )
            fav["comentarios"] = cursor.fetchall()

    finally:
        cursor.close()
        conn.close()

    return templates.TemplateResponse("favorites.html", {
        "request": request,
        "user": user,
        "active_page": "favorites",
        "favorites": favorites,
        "message": message,
    })


# ══════════════════════════════════════════════════════════
#  ROTA DE ADMINISTRAÇÃO — CONSULTA DE LOGS (Atividade 5)
# ══════════════════════════════════════════════════════════

@app.get("/admin/logs", response_class=HTMLResponse)
async def admin_logs_page(request: Request, limit: int = 50, message: str = None):
    """
    Página de consulta de logs de auditoria — apenas admin.
    O catalog-service valida RBAC localmente e repassa a chamada
    para o log-service interno via httpx.
    """
    user = await _get_user_or_none(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # ── Enforcement de RBAC ──
    if user.get("role", "user") != "admin":
        # Evento de auditoria: tentativa de acesso negado
        await _emit_log(
            usuario_id=user["id"],
            acao="acesso_negado_403",
            detalhe="tentativa de acessar /admin/logs sem permissão",
            ip_origem=_get_client_ip(request),
        )
        raise HTTPException(
            status_code=403,
            detail="Acesso negado: somente administradores.",
        )

    # ── Repassar chamada ao log-service interno ──
    logs = []
    error = None
    try:
        token = request.cookies.get("access_token", "")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{LOG_SERVICE_URL}/logs",
                params={"limit": limit},
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                logs = data.get("logs", [])
            else:
                error = f"Erro ao consultar log-service: HTTP {resp.status_code}"
    except Exception as e:
        error = f"Log-service indisponível: {e}"

    return templates.TemplateResponse("admin_logs.html", {
        "request": request,
        "user": user,
        "active_page": "admin_logs",
        "logs": logs,
        "limit": limit,
        "message": message,
        "error": error,
    })


# ══════════════════════════════════════════════════════════
#  ROTAS DE PERFIL DE USUÁRIO — MinIO (Atividade 6)
# ══════════════════════════════════════════════════════════

@app.get("/profile/{profile_user_id}", response_class=HTMLResponse)
async def profile_page(request: Request, profile_user_id: int, message: str = None, error: str = None):
    """
    Página de perfil pública: exibe foto (do MinIO), bio e filmes favoritados.
    O botão de edição só é renderizado quando o usuário logado é o dono do perfil.
    """
    user = await _get_user_or_none(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Buscar dados do usuário de perfil no banco
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, nome, email, role, bio, avatar_key FROM usuarios WHERE id = %s",
            (profile_user_id,),
        )
        profile_user = cursor.fetchone()
        if not profile_user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")

        # Buscar filmes favoritados pelo dono do perfil
        cursor.execute(
            """SELECT tmdb_movie_id, titulo, poster_path, criado_em
               FROM favoritos WHERE usuario_id = %s ORDER BY criado_em DESC""",
            (profile_user_id,),
        )
        favorites = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    # Montar URL do avatar via proxy interno /storage/avatars/<filename>
    avatar_url = None
    if profile_user.get("avatar_key"):
        # Extrai apenas o nome do arquivo da chave (ex: "avatars/42-xxx.jpg" → "42-xxx.jpg")
        filename = profile_user["avatar_key"].split("/", 1)[-1]
        avatar_url = f"/storage/avatars/{filename}"

    is_own_profile = (user["id"] == profile_user_id)

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "active_page": "profile",
        "profile_user": profile_user,
        "avatar_url": avatar_url,
        "favorites": favorites,
        "is_own_profile": is_own_profile,
        "message": message,
        "error": error,
    })


@app.post("/profile/{profile_user_id}/upload")
async def profile_upload(
    request: Request,
    profile_user_id: int,
    bio: str = Form(""),
    foto: UploadFile = File(None),
):
    """
    Atualiza bio e/ou foto de perfil do usuário.
    Segurança:
      - O usuário SÓ pode editar o próprio perfil.
      - O user_id é extraído do JWT/sessão. O :id da URL é apenas para roteamento.
      - Validação de MIME type e tamanho no backend (nunca confiar apenas no frontend).
    """
    user = await _get_user_or_none(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # ── Isolamento rígido: NUNCA confiar no ID da URL para autorizar edição ──
    if user["id"] != profile_user_id:
        await _emit_log(
            usuario_id=user["id"],
            acao="audit.security.access_denied",
            detalhe=f"tentativa de editar perfil do usuario_id={profile_user_id} (403)",
            ip_origem=_get_client_ip(request),
        )
        raise HTTPException(
            status_code=403,
            detail="Acesso negado: você só pode editar o seu próprio perfil.",
        )

    new_avatar_key = None

    # ── Processar upload de imagem (se enviado) ──
    if foto and foto.filename:
        # Validação de MIME type no backend
        if foto.content_type not in ALLOWED_MIME_TYPES:
            return RedirectResponse(
                url=f"/profile/{profile_user_id}?error=Tipo+de+arquivo+inválido.+Envie+uma+imagem+JPEG,+PNG,+WEBP+ou+GIF.",
                status_code=302,
            )

        file_bytes = await foto.read()

        # Validação de tamanho no backend (≤ 3 MB)
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            return RedirectResponse(
                url=f"/profile/{profile_user_id}?error=Arquivo+muito+grande.+Limite+máximo:+3+MB.",
                status_code=302,
            )

        # Buscar avatar antigo para remover (evitar objetos órfãos no MinIO)
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT avatar_key FROM usuarios WHERE id = %s", (user["id"],))
            row = cursor.fetchone()
            old_key = row["avatar_key"] if row else None
        finally:
            cursor.close()
            conn.close()

        # Upload da nova imagem para o MinIO
        try:
            new_avatar_key = upload_avatar(
                user_id=user["id"],
                file_bytes=file_bytes,
                filename=foto.filename,
                content_type=foto.content_type,
            )
        except S3Error as e:
            return RedirectResponse(
                url=f"/profile/{profile_user_id}?error=Erro+ao+enviar+imagem+para+o+storage.",
                status_code=302,
            )

        # Remover avatar anterior do MinIO (best-effort)
        if old_key:
            delete_avatar(old_key)

    # ── Persistir bio e/ou nova chave do avatar no MariaDB ──
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if new_avatar_key:
            cursor.execute(
                "UPDATE usuarios SET bio = %s, avatar_key = %s WHERE id = %s",
                (bio.strip() or None, new_avatar_key, user["id"]),
            )
        else:
            # Só a bio foi enviada — não apaga o avatar existente
            cursor.execute(
                "UPDATE usuarios SET bio = %s WHERE id = %s",
                (bio.strip() or None, user["id"]),
            )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    # ── Evento de auditoria: atualização de perfil ──
    await _emit_log(
        usuario_id=user["id"],
        acao="perfil.atualizado",
        detalhe=f"bio_atualizada={'sim' if bio.strip() else 'nao'}, foto_atualizada={'sim' if new_avatar_key else 'nao'}",
        ip_origem=_get_client_ip(request),
    )

    return RedirectResponse(
        url=f"/profile/{profile_user_id}?message=Perfil+atualizado+com+sucesso!",
        status_code=302,
    )


@app.get("/storage/avatars/{filename}")
async def serve_avatar(filename: str):
    """
    Proxy interno para servir imagens armazenadas no MinIO.
    O MinIO não expõe porta pública no host; o catalog-service faz o proxy.
    Isso segue o mesmo padrão do proxy /grafana descrito no auxiliar.
    """
    key = f"avatars/{filename}"
    try:
        response = stream_avatar(key)
        content_type = response.headers.get("Content-Type", "image/jpeg")
        data = response.read()
        response.close()
        response.release_conn()
        return Response(content=data, media_type=content_type)
    except S3Error:
        raise HTTPException(status_code=404, detail="Imagem não encontrada.")
