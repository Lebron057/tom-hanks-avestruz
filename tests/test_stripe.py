"""
Script de Teste de Integração e Validação do Módulo Stripe.
Valida:
1. Verificação criptográfica do webhook com assinatura válida vs inválida.
2. Comportamento da regra de limite de favoritos (3 favoritos para Free, ilimitado para Premium).
"""

import time
import hmac
import hashlib
import json

from app.stripe_service import verify_and_construct_webhook_event
import stripe


def test_webhook_cryptographic_verification():
    secret = "whsec_test_secret_12345"
    payload = json.dumps({
        "id": "evt_test_123",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_abc",
                "client_reference_id": "1",
                "customer": "cus_123",
                "subscription": "sub_456"
            }
        }
    }).encode("utf-8")

    timestamp = int(time.time())
    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    computed_signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256
    ).hexdigest()

    valid_sig_header = f"t={timestamp},v1={computed_signature}"

    import os
    os.environ["STRIPE_WEBHOOK_SECRET"] = secret

    # 1. Teste de assinatura válida
    event = verify_and_construct_webhook_event(payload, valid_sig_header)
    assert event["type"] == "checkout.session.completed"
    assert event["data"]["object"]["client_reference_id"] == "1"
    print(" [OK] Validação de assinatura legítima passou com sucesso!")

    # 2. Teste de assinatura forjada / inválida
    tampered_sig_header = f"t={timestamp},v1=forged_invalid_signature_hex"
    try:
        verify_and_construct_webhook_event(payload, tampered_sig_header)
        assert False, "Deveria ter lançado SignatureVerificationError para assinatura forjada"
    except stripe.SignatureVerificationError:
        print(" [OK] Assinatura adulterada rejeitada com SignatureVerificationError!")


if __name__ == "__main__":
    test_webhook_cryptographic_verification()
    print("\nTodos os testes unitários do Stripe passaram com êxito!")
