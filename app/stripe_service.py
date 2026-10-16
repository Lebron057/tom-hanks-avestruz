"""
Módulo de Integração com a Stripe (Modo de Teste) - Atividade 7.
Gerencia a criação de Checkout Sessions e a validação de assinaturas de Webhooks.
Nenhuma informação de cartão de crédito passa ou é armazenada pela nossa aplicação.
"""

import os
from typing import Optional
import stripe

STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
stripe.api_key = STRIPE_API_KEY


def is_stripe_configured() -> bool:
    """Verifica se a chave de API do Stripe está configurada."""
    return bool(STRIPE_API_KEY and not STRIPE_API_KEY.startswith("sk_test_placeholder"))


def create_premium_checkout_session(
    usuario_id: int,
    user_email: str,
    user_nome: str,
    base_url: str,
) -> stripe.checkout.Session:
    """
    Cria uma Checkout Session no Stripe (Modo de Teste) para assinatura do Plano Premium.
    Redireciona para o checkout hospedado pelo Stripe.
    """
    if not is_stripe_configured():
        raise ValueError("Stripe API Key não configurada. Defina STRIPE_API_KEY no arquivo .env.")

    stripe.api_key = STRIPE_API_KEY

    # Monta URLs de retorno
    success_url = f"{base_url.rstrip('/')}/catalog?premium_success=true"
    cancel_url = f"{base_url.rstrip('/')}/profile/{usuario_id}?canceled=true"

    session_params = {
        "payment_method_types": ["card"],
        "mode": "subscription",
        "line_items": [
            {
                "price_data": {
                    "currency": "brl",
                    "product_data": {
                        "name": "Plano Premium — Catálogo Tom Hanks",
                        "description": "Favoritos ilimitados, selo VIP no perfil e acesso antecipado a novos recursos.",
                    },
                    "unit_amount": 1990,  # R$ 19,90 / mês
                    "recurring": {
                        "interval": "month",
                    },
                },
                "quantity": 1,
            }
        ],
        "client_reference_id": str(usuario_id),
        "metadata": {
            "usuario_id": str(usuario_id),
            "user_nome": user_nome,
        },
        "success_url": success_url,
        "cancel_url": cancel_url,
    }

    # Apenas repassa customer_email pré-preenchido se tiver formato válido com TLD (.com, etc.)
    # Caso contrário, o Stripe Checkout permite ao cliente preencher o e-mail de faturamento com segurança
    if user_email and "@" in user_email and "." in user_email.split("@")[-1]:
        session_params["customer_email"] = user_email

    session = stripe.checkout.Session.create(**session_params)
    return session


def verify_and_construct_webhook_event(
    payload: bytes,
    sig_header: str,
) -> stripe.Event:
    """
    Valida a assinatura criptográfica do Webhook da Stripe usando o Webhook Secret.
    Garante que requisições forjadas ou sem assinatura sejam prontamente rejeitadas.
    """
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret or webhook_secret.startswith("whsec_placeholder"):
        raise ValueError("STRIPE_WEBHOOK_SECRET não configurado.")

    stripe.api_key = STRIPE_API_KEY
    return stripe.Webhook.construct_event(
        payload=payload,
        sig_header=sig_header,
        secret=webhook_secret,
    )
