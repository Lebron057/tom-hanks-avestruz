import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_password_reset_email(to_email: str, user_name: str, reset_token: str, reset_base_url: str | None = None) -> bool:
    """
    Envia e-mail com o link de recuperação de senha utilizando SMTP (Mailtrap).
    Lê todas as configurações exclusivamente das variáveis de ambiente.
    """
    smtp_host = os.getenv("SMTP_HOST", "sandbox.smtp.mailtrap.io")
    smtp_port = int(os.getenv("SMTP_PORT", "2525"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", "noreply@catalogofilmes.com")

    # URL base para o reset de senha (ponto público de entrada)
    app_port = os.getenv("APP_PORT", "8000")
    if not reset_base_url:
        reset_base_url = os.getenv("PUBLIC_APP_URL", f"http://localhost:{app_port}")

    reset_link = f"{reset_base_url.rstrip('/')}/reset-password?token={reset_token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Recuperação de Senha — Catálogo de Filmes Tom Hanks"
    msg["From"] = smtp_from
    msg["To"] = to_email

    text_content = f"""Olá, {user_name}!

Você solicitou a redefinição de senha para sua conta no Catálogo de Filmes Tom Hanks.

Para cadastrar uma nova senha, utilize o link abaixo:
{reset_link}

Atenção:
- Este link é de uso único.
- Ele é válido exclusivamente pelos próximos 30 minutos.

Se você não solicitou esta alteração, desconsidere este e-mail.
"""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: #1e293b; padding: 30px; border-radius: 12px; border: 1px solid #334155; }}
            .header {{ text-align: center; border-bottom: 1px solid #334155; padding-bottom: 20px; }}
            .header h1 {{ color: #38bdf8; margin: 0; font-size: 24px; }}
            .content {{ padding: 25px 0; line-height: 1.6; color: #cbd5e1; }}
            .btn {{ display: inline-block; padding: 12px 28px; background: linear-gradient(135deg, #38bdf8, #2563eb); color: #ffffff !important; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 20px 0; text-align: center; }}
            .token-box {{ background: #0f172a; padding: 12px; border-radius: 6px; font-family: monospace; word-break: break-all; color: #94a3b8; font-size: 13px; }}
            .footer {{ border-top: 1px solid #334155; padding-top: 15px; font-size: 12px; color: #64748b; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎬 Catálogo Tom Hanks</h1>
            </div>
            <div class="content">
                <p>Olá, <strong>{user_name}</strong>,</p>
                <p>Recebemos uma solicitação para redefinir a senha da sua conta.</p>
                <p style="text-align: center;">
                    <a href="{reset_link}" class="btn" target="_blank">Redefinir Minha Senha</a>
                </p>
                <p>Ou copie e cole o link no seu navegador:</p>
                <div class="token-box">{reset_link}</div>
                <p style="margin-top: 20px; font-size: 14px; color: #f59e0b;">
                    ⚠️ <strong>Importante:</strong> Este link é de uso único e expira em <strong>30 minutos</strong>.
                </p>
            </div>
            <div class="footer">
                <p>Se você não fez esta solicitação, ignore este e-mail com segurança.</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            if smtp_port in (587, 2525):
                try:
                    server.starttls()
                except Exception:
                    pass

            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)

            server.sendmail(smtp_from, [to_email], msg.as_string())
            print(f"[AuthService - Mailer] E-mail de reset enviado com sucesso para {to_email}")
            return True
    except Exception as e:
        print(f"[AuthService - Mailer] Erro ao enviar e-mail via SMTP ({smtp_host}:{smtp_port}): {e}")
        # Retorna False mas não quebra o fluxo para possibilitar tratamento
        return False
