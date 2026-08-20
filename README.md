# 🎬 Catálogo de Filmes — Tom Hanks

Aplicação web que permite explorar a filmografia de Tom Hanks, favoritar filmes e deixar comentários pessoais. Cada usuário tem seus dados isolados (favoritos e comentários não são compartilhados entre contas).

professor: @siriani

---

## Funcionalidades

- 🔐 **Cadastro e Login** com autenticação JWT e senhas criptografadas (bcrypt)
- 🎞️ **Catálogo de filmes** buscados em tempo real da API TMDB (pôster, título, sinopse)
- ⭐ **Favoritar filmes** — persistido no MariaDB, vinculado ao usuário
- 💬 **Comentários por filme** — visíveis apenas para quem escreveu
- 🛡️ **Isolamento total** entre contas de usuários diferentes (proteção IDOR)

---

## Stack

| Camada        | Tecnologia                  |
|---------------|-----------------------------|
| Backend       | Python 3.11 + FastAPI       |
| Frontend      | Jinja2 (server-side render) |
| Banco de Dados| MariaDB                     |
| Autenticação  | JWT (python-jose) + bcrypt  |
| API Externa   | TMDB (The Movie Database)   |
| Deploy        | Docker + Portainer          |

---

## Como rodar localmente

### 1. Clonar o repositório

```bash
git clone <url-do-repo>
cd atividade2
```

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
# Preencha os valores no arquivo .env
```

### 3. Rodar com Docker Compose

```bash
docker-compose up --build
```

A aplicação ficará disponível em `http://localhost:8000` (ou na porta definida em `APP_PORT`).

---

## Variáveis de ambiente

| Variável       | Descrição                          |
|----------------|------------------------------------|
| `TMDB_API_KEY` | Chave de API do TMDB               |
| `DB_HOST`      | Host do MariaDB                    |
| `DB_PORT`      | Porta do MariaDB (padrão: 3306)    |
| `DB_USER`      | Usuário do MariaDB                 |
| `DB_PASSWORD`  | Senha do MariaDB                   |
| `DB_NAME`      | Nome do banco de dados             |
| `SECRET_KEY`   | Chave secreta para assinatura JWT  |
| `APP_PORT`     | Porta pública do container         |

---

## Estrutura do projeto

```
├── app/
│   ├── main.py          # Rotas FastAPI
│   ├── database.py      # Conexão e init do MariaDB
│   ├── auth.py          # JWT + bcrypt
│   ├── tmdb.py          # Cliente HTTP para TMDB
│   ├── templates/       # HTML (Jinja2)
│   └── static/          # CSS
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```
