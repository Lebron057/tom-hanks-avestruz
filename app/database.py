import os
import mysql.connector
from mysql.connector import Error


def get_connection():
    """Cria e retorna uma conexão com o MariaDB usando variáveis de ambiente."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "catalogo_filmes"),
    )


def init_db():
    """Cria as tabelas necessárias caso não existam e aplica migrações de schema."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Tabela de Usuários com controle de role
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nome VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            senha_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'user',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migração segura: garante que a coluna 'role' exista se a tabela já foi criada anteriormente
    try:
        cursor.execute("SHOW COLUMNS FROM usuarios LIKE 'role'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE usuarios ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'")
    except Exception as e:
        print(f"Aviso ao verificar/adicionar coluna role: {e}")

    # 2. Tabela de Tokens para Reset de Senha (expiração e controle de uso)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reset_tokens (
            id INT AUTO_INCREMENT PRIMARY KEY,
            usuario_id INT NOT NULL,
            token VARCHAR(255) UNIQUE NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expira_em DATETIME NOT NULL,
            usado BOOLEAN NOT NULL DEFAULT FALSE,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
    """)

    # 3. Tabela de Favoritos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favoritos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            usuario_id INT NOT NULL,
            tmdb_movie_id INT NOT NULL,
            titulo VARCHAR(255) NOT NULL,
            poster_path VARCHAR(255),
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            UNIQUE (usuario_id, tmdb_movie_id)
        )
    """)

    # 4. Tabela de Comentários
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comentarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            usuario_id INT NOT NULL,
            tmdb_movie_id INT NOT NULL,
            texto TEXT NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()

