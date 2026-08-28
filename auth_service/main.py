"""
Microsserviço de Autenticação (auth-service)
Responsável exclusivamente por:
- Registro de novos usuários e controle de papéis (user/admin)
- Login e emissão de tokens JWT
- Validação de sessão / tokens
- Fluxo completo de recuperação de senha com tokens de 30 minutos e envio SMTP (Mailtrap)
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, status, Query, Header
from fastapi.middleware.cors import CORSMiddleware

from auth_service.database import get_connection, init_db
from auth_service.models import (
    RegisterRequest,
    LoginRequest,
    VerifyTokenRequest,
    ForgotPasswordRequest,
    ValidateResetTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    GenericResponse,
)
from auth_service.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_reset_token,
)
from auth_service.mailer import send_password_reset_email


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialização do banco de dados na inicialização do serviço
    try:
        init_db()
        print("[AuthService] Banco de dados inicializado com sucesso.")
    except Exception as e:
        print(f"[AuthService] Erro ao conectar/inicializar banco de dados: {e}")
    yield


app = FastAPI(
    title="Auth Service — Microsserviço de Autenticação",
    description="Serviço privado de autenticação, papéis e recuperação de senha.",
    version="1.0.0",
    lifespan=lifespan,
)

# Permitir chamadas internas CORS se necessário
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Endpoint de verificação de saúde do serviço."""
    return {"status": "ok", "service": "auth-service"}


# ══════════════════════════════════════════════════════════
#  1. REGISTRO DE USUÁRIO
# ══════════════════════════════════════════════════════════
@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest):
    """
    Registra um novo usuário com papel (role) atribuído.
    Gera hash bcrypt da senha e persiste no MariaDB.
    """
    if len(data.senha) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha deve ter no mínimo 6 caracteres.",
        )

    # Validar role (padrão 'user', permitindo 'admin')
    user_role = data.role.strip().lower()
    if user_role not in ("user", "admin"):
        user_role = "user"

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Verificar se e-mail já existe
        cursor.execute("SELECT id FROM usuarios WHERE email = %s", (data.email.strip().lower(),))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este e-mail já está cadastrado.",
            )

        senha_hash = hash_password(data.senha)
        cursor.execute(
            """INSERT INTO usuarios (nome, email, senha_hash, role)
               VALUES (%s, %s, %s, %s)""",
            (data.nome.strip(), data.email.strip().lower(), senha_hash, user_role),
        )
        conn.commit()
        novo_id = cursor.lastrowid

        return {
            "status": "success",
            "message": "Conta criada com sucesso!",
            "user": {
                "id": novo_id,
                "nome": data.nome.strip(),
                "email": data.email.strip().lower(),
                "role": user_role,
            },
        }
    finally:
        cursor.close()
        conn.close()


# ══════════════════════════════════════════════════════════
#  2. LOGIN E EMISSÃO DE SESSÃO (JWT)
# ══════════════════════════════════════════════════════════
@app.post("/auth/login", response_model=TokenResponse)
async def login(data: LoginRequest):
    """
    Valida credenciais do usuário e retorna token JWT com role embutida.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT id, nome, email, senha_hash, role FROM usuarios WHERE email = %s",
            (data.email.strip().lower(),),
        )
        usuario = cursor.fetchone()

        if not usuario or not verify_password(data.senha, usuario["senha_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="E-mail ou senha incorretos.",
            )

        user_role = usuario.get("role") or "user"
        token = create_access_token(
            usuario_id=usuario["id"],
            nome=usuario["nome"],
            email=usuario["email"],
            role=user_role,
        )

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse(
                id=usuario["id"],
                nome=usuario["nome"],
                email=usuario["email"],
                role=user_role,
            ),
        )
    finally:
        cursor.close()
        conn.close()


# ══════════════════════════════════════════════════════════
#  3. VALIDAÇÃO DE SESSÃO / TOKEN
# ══════════════════════════════════════════════════════════
@app.post("/auth/verify", response_model=UserResponse)
@app.get("/auth/verify", response_model=UserResponse)
async def verify_session(
    token_body: Optional[VerifyTokenRequest] = None,
    authorization: Optional[str] = Header(None),
    token_param: Optional[str] = Query(None, alias="token"),
):
    """
    Valida o token JWT e retorna os dados do usuário autenticado.
    Suporta envio via Body, Header Authorization (Bearer) ou Query Param.
    """
    token = None
    if token_body and token_body.token:
        token = token_body.token
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1].strip()
    elif token_param:
        token = token_param

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso não fornecido.",
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
        )

    return UserResponse(
        id=int(payload["sub"]),
        nome=payload.get("nome", ""),
        email=payload.get("email", ""),
        role=payload.get("role", "user"),
    )


# ══════════════════════════════════════════════════════════
#  4. ESQUECI MINHA SENHA (SOLICITAÇÃO & DISPARO SMTP)
# ══════════════════════════════════════════════════════════
@app.post("/auth/forgot-password", response_model=GenericResponse)
async def forgot_password(data: ForgotPasswordRequest):
    """
    Inicia o fluxo de recuperação de senha:
    - Gera token único criptográfico.
    - Grava na tabela reset_tokens com validade de 30 minutos e usado=False.
    - Dispara e-mail real via SMTP (Mailtrap) com o link de recuperação.
    """
    email_clean = data.email.strip().lower()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, nome, email FROM usuarios WHERE email = %s", (email_clean,))
        usuario = cursor.fetchone()

        if usuario:
            # Gerar token seguro
            token = generate_reset_token()
            # Validade estrita de 30 minutos
            expira_em = datetime.now() + timedelta(minutes=30)

            # Inserir no banco
            cursor.execute(
                """INSERT INTO reset_tokens (usuario_id, token, expira_em, usado)
                   VALUES (%s, %s, %s, FALSE)""",
                (usuario["id"], token, expira_em),
            )
            conn.commit()

            # Disparo real de e-mail via SMTP Mailtrap
            send_password_reset_email(
                to_email=usuario["email"],
                user_name=usuario["nome"],
                reset_token=token,
                reset_base_url=data.base_url,
            )

        # Resposta genérica para evitar enumeração de contas
        return GenericResponse(
            status="success",
            message="Se o e-mail informado estiver cadastrado, as instruções e o link de recuperação foram enviados.",
        )
    finally:
        cursor.close()
        conn.close()


# ══════════════════════════════════════════════════════════
#  5. VALIDAÇÃO RÍGIDA DO TOKEN DE RECUPERAÇÃO
# ══════════════════════════════════════════════════════════
@app.get("/auth/reset-password/validate")
@app.post("/auth/reset-password/validate")
async def validate_reset_token(
    token_param: Optional[str] = Query(None, alias="token"),
    token_body: Optional[ValidateResetTokenRequest] = None,
):
    """
    Validação estrita do token de reset:
    1. Verifica existência no banco.
    2. Ineditismo de uso: rejeita se usado == True.
    3. Validade temporal: rejeita se agora > expira_em (30 min).
    """
    token = token_param or (token_body.token if token_body else None)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token não fornecido.",
        )

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """SELECT r.id, r.usuario_id, r.expira_em, r.usado, u.email, u.nome
               FROM reset_tokens r
               JOIN usuarios u ON u.id = r.usuario_id
               WHERE r.token = %s""",
            (token,),
        )
        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token de recuperação inexistente ou inválido.",
            )

        if row["usado"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este link de recuperação já foi utilizado anteriormente.",
            )

        # Validação de tempo (30 minutos)
        if datetime.now() > row["expira_em"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este link de recuperação expirou. Solicite um novo link.",
            )

        return {
            "valid": True,
            "usuario_id": row["usuario_id"],
            "email": row["email"],
            "nome": row["nome"],
            "message": "Token válido para redefinição de senha.",
        }
    finally:
        cursor.close()
        conn.close()


# ══════════════════════════════════════════════════════════
#  6. EFETIVAÇÃO DA TROCA DE SENHA
# ══════════════════════════════════════════════════════════
@app.post("/auth/reset-password", response_model=GenericResponse)
async def reset_password(data: ResetPasswordRequest):
    """
    Executa a troca de senha com validação rígida:
    - Valida token (existência, não usado, não expirado).
    - Atualiza senha_hash do usuário.
    - Invalida o token marcando usado = TRUE.
    """
    if len(data.nova_senha) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve ter no mínimo 6 caracteres.",
        )

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """SELECT id, usuario_id, expira_em, usado
               FROM reset_tokens
               WHERE token = %s""",
            (data.token,),
        )
        token_record = cursor.fetchone()

        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token de recuperação inexistente ou inválido.",
            )

        if token_record["usado"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este link de recuperação já foi utilizado anteriormente.",
            )

        if datetime.now() > token_record["expira_em"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este link de recuperação expirou (validade de 30 minutos). Solicite um novo.",
            )

        # Gerar novo hash de senha
        nova_senha_hash = hash_password(data.nova_senha)
        usuario_id = token_record["usuario_id"]

        # Atualizar a senha do usuário
        cursor.execute(
            "UPDATE usuarios SET senha_hash = %s WHERE id = %s",
            (nova_senha_hash, usuario_id),
        )

        # Invalidar o token de recuperação (ineditismo de uso garantido)
        cursor.execute(
            "UPDATE reset_tokens SET usado = TRUE WHERE id = %s",
            (token_record["id"],),
        )

        conn.commit()

        return GenericResponse(
            status="success",
            message="Senha redefinida com sucesso! Faça login com sua nova senha.",
        )
    finally:
        cursor.close()
        conn.close()
