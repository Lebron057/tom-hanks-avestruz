"""
Catálogo de Filmes — Tom Hanks
FastAPI application com autenticação JWT, integração TMDB e MariaDB.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import init_db, get_connection
from app.auth import hash_password, verify_password, create_token, get_current_user
from app.tmdb import get_tom_hanks_movies


# ── Lifespan ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: cria tabelas no banco
    init_db()
    yield


app = FastAPI(title="Catálogo Tom Hanks", lifespan=lifespan)

# Montar arquivos estáticos e templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# ── Helpers ─────────────────────────────────────────────
def _get_user_or_none(request: Request) -> dict | None:
    """Tenta extrair o usuário do cookie, retorna None se não autenticado."""
    try:
        return get_current_user(request)
    except HTTPException:
        return None


# ══════════════════════════════════════════════════════════
#  ROTAS PÚBLICAS
# ══════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, success: str = None, error: str = None):
    user = _get_user_or_none(request)
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
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, nome, senha_hash FROM usuarios WHERE email = %s", (email,))
        usuario = cursor.fetchone()

        if not usuario or not verify_password(senha, usuario["senha_hash"]):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "user": None,
                "error": "E-mail ou senha incorretos.",
            })

        token = create_token(usuario["id"], usuario["nome"])
        response = RedirectResponse(url="/catalog", status_code=302)
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=86400,  # 24 horas
        )
        return response

    finally:
        cursor.close()
        conn.close()


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = None):
    user = _get_user_or_none(request)
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

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Verificar se o e-mail já existe
        cursor.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
        if cursor.fetchone():
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Este e-mail já está cadastrado.",
            })

        senha_hash = hash_password(senha)
        cursor.execute(
            "INSERT INTO usuarios (nome, email, senha_hash) VALUES (%s, %s, %s)",
            (nome, email, senha_hash),
        )
        conn.commit()

        return RedirectResponse(
            url="/login?success=Conta+criada+com+sucesso!+Faça+login.",
            status_code=302,
        )

    finally:
        cursor.close()
        conn.close()


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# ══════════════════════════════════════════════════════════
#  ROTAS PROTEGIDAS
# ══════════════════════════════════════════════════════════

@app.get("/catalog", response_class=HTMLResponse)
async def catalog_page(request: Request, message: str = None):
    user = _get_user_or_none(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Buscar filmes da TMDB
    try:
        movies = await get_tom_hanks_movies()
    except Exception as e:
        movies = []
        message = f"Erro ao buscar filmes: {e}"

    # Buscar IDs dos filmes favoritados pelo usuário
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
    user = _get_user_or_none(request)
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
    user = _get_user_or_none(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Proteção IDOR: sempre filtra por usuario_id
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
    user = _get_user_or_none(request)
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
    redirect_url = "/favorites?message=Comentário+adicionado!" if "favorites" in referer else "/catalog?message=Comentário+adicionado!"
    return RedirectResponse(url=redirect_url, status_code=302)


@app.post("/comment/{comment_id}/remove")
async def remove_comment(request: Request, comment_id: int):
    user = _get_user_or_none(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Proteção IDOR: só apaga se pertence ao usuário logado
        cursor.execute(
            "DELETE FROM comentarios WHERE id = %s AND usuario_id = %s",
            (comment_id, user["id"]),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return RedirectResponse(url="/favorites?message=Comentário+removido!", status_code=302)


@app.get("/favorites", response_class=HTMLResponse)
async def favorites_page(request: Request, message: str = None):
    user = _get_user_or_none(request)
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

        # Buscar comentários do usuário para cada filme favoritado
        for fav in favorites:
            cursor.execute(
                """SELECT id, texto, criado_em FROM comentarios
                   WHERE usuario_id = %s AND tmdb_movie_id = %s
                   ORDER BY criado_em ASC""",
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
