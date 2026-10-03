"""
Cliente MinIO (Object Storage compatível com S3) — Atividade 6
Responsabilidades:
  - Inicializar o cliente MinIO com credenciais via variáveis de ambiente.
  - Garantir que o bucket 'avatars' exista com política de leitura pública.
  - Fornecer funções de upload, remoção e streaming de objetos.
  - Gerar chaves de objeto únicas e previsíveis para evitar colisões de nome.
"""

import io
import os
import secrets
import time
from typing import Optional

from minio import Minio
from minio.commonconfig import ENABLED
from minio.error import S3Error

# ── Configuração via variáveis de ambiente ──────────────────────────────────
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "avatars")

# Determina se a conexão é segura (TLS). Em desenvolvimento local, é HTTP.
_secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

# Cliente singleton (instanciado na inicialização da aplicação)
_client: Optional[Minio] = None


def get_minio_client() -> Minio:
    """Retorna o cliente MinIO, criando-o se ainda não existir."""
    global _client
    if _client is None:
        _client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=_secure,
            # Garage exige path-style (http://host:port/bucket/object)
            # em vez de virtual-host-style (http://bucket.host:port/object)
        )
    return _client


def ensure_bucket() -> None:
    """
    Garante que o bucket de avatares exista e tenha política de leitura pública.
    Estratégia escolhida: Bucket com leitura pública (Opção A da atividade).
    Veja README.md para justificativa e trade-offs.
    """
    client = get_minio_client()
    try:
        if not client.bucket_exists(MINIO_BUCKET):
            client.make_bucket(MINIO_BUCKET)
            print(f"[MinIO] Bucket '{MINIO_BUCKET}' criado.")

        # Política de leitura pública — só GetObject (download), nunca escrita
        public_policy = f"""{{
            "Version": "2012-10-17",
            "Statement": [
                {{
                    "Effect": "Allow",
                    "Principal": {{"AWS": ["*"]}},
                    "Action": ["s3:GetObject"],
                    "Resource": ["arn:aws:s3:::{MINIO_BUCKET}/*"]
                }}
            ]
        }}"""
        try:
            client.set_bucket_policy(MINIO_BUCKET, public_policy)
            print(f"[MinIO] Bucket '{MINIO_BUCKET}' pronto (leitura pública).")
        except S3Error as policy_err:
            # Garage v0.9 tem suporte limitado a bucket policies — não é fatal
            print(f"[MinIO] Aviso: não foi possível definir policy pública: {policy_err}")
            print(f"[MinIO] Bucket '{MINIO_BUCKET}' pronto (policy ignorada).")
    except S3Error as e:
        print(f"[MinIO] Erro ao preparar bucket: {e}")
        raise


def generate_object_key(user_id: int, original_filename: str) -> str:
    """
    Gera uma chave de objeto única e previsível para evitar colisões.
    Formato: avatars/{userId}-{timestamp}-{hex}.{ext}
    """
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "jpg"
    random_hex = secrets.token_hex(6)
    timestamp = int(time.time())
    return f"avatars/{user_id}-{timestamp}-{random_hex}.{ext}"


def upload_avatar(user_id: int, file_bytes: bytes, filename: str, content_type: str) -> str:
    """
    Envia os bytes da imagem para o MinIO e retorna a chave do objeto gravado.
    O MariaDB deve armazenar apenas essa chave, nunca o binário.

    Args:
        user_id: ID do usuário dono do avatar.
        file_bytes: Conteúdo binário da imagem.
        filename: Nome original do arquivo (para extrair extensão).
        content_type: MIME type da imagem (ex: image/jpeg).

    Returns:
        Chave do objeto no MinIO (ex: "avatars/42-1727123456-abc123.jpg").
    """
    client = get_minio_client()
    key = generate_object_key(user_id, filename)

    client.put_object(
        bucket_name=MINIO_BUCKET,
        object_name=key,
        data=io.BytesIO(file_bytes),
        length=len(file_bytes),
        content_type=content_type,
    )
    return key


def delete_avatar(avatar_key: str) -> None:
    """
    Remove um objeto do MinIO pelo sua chave.
    Ao trocar de foto, a anterior é removida para não deixar objetos órfãos.
    Falhas são silenciosas (best-effort).
    """
    if not avatar_key:
        return
    try:
        client = get_minio_client()
        client.remove_object(MINIO_BUCKET, avatar_key)
    except S3Error as e:
        print(f"[MinIO] Aviso ao remover objeto '{avatar_key}': {e}")


def stream_avatar(avatar_key: str):
    """
    Retorna o objeto (resposta HTTP do MinIO) para streaming via proxy.
    Usado pela rota /storage/avatars/<filename>.
    Lança S3Error se o objeto não for encontrado.
    """
    client = get_minio_client()
    return client.get_object(MINIO_BUCKET, avatar_key)
