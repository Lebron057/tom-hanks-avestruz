"""
Catálogo de Filmes — Tom Hanks (Catalog Service)
Ponto de entrada público da aplicação.
Responsabilidades:
- Interface do usuário (Jinja2 SSR) e arquivos estáticos.
- Integração com a API do TMDB para catálogo ao vivo de filmes.
- Persistência e segregação de favoritos e comentários por usuário no MariaDB.
- Delegação de autenticação, papéis e recuperação de senha ao auth-service privado.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
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


# ── Lifespan ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: garante que as tabelas de favoritos e comentários existam
    try:
        init_db()
    except Exception as e:
        print(f"[CatalogService] Aviso ao inicializar banco: {e}")
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
async def logout():
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
            raise HTTPException(
                status_code=403,
                detail="Acesso negado: você não tem permissão para apagar este comentário.",
            )

        cursor.execute("DELETE FROM comentarios WHERE id = %s", (comment_id,))
        conn.commit()
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

