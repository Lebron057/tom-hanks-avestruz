# Catálogo de Filmes — Tom Hanks

> Especificação para agente de IA implementar o projeto completo.

## Stack obrigatória

**Este projeto deve ser implementado em Python.**

Sugestão de stack (adaptável, mas mantendo o espírito "backend Python + banco relacional"):

- **Backend:** FastAPI (ou Flask) servindo tanto a API quanto as rotas de autenticação
- **Frontend:** pode ser server-side rendered (Jinja2) ou um HTML/JS simples consumindo a API do próprio backend — mas nunca chamando TMDB ou MariaDB diretamente do navegador
- **Banco de dados:** MariaDB, acessado via `mysql-connector-python` ou `SQLAlchemy`
- **Autenticação:** sessão própria da aplicação (ex: JWT ou cookies de sessão), com senha armazenada com hash (ex: `passlib`/`bcrypt`)
- **Cliente HTTP para TMDB:** `httpx` ou `requests`, chamado sempre a partir do backend
- **Empacotamento:** Dockerfile + docker-compose.yml (se necessário) para publicar no Portainer

## Objetivo

Construir uma aplicação que busca filmes com Tom Hanks numa API externa (TMDB) e permite que cada usuário favorite e comente filmes — sem misturar os dados de um usuário com os de outro.

## Prazo

**Entrega: quinta-feira, 20/08/2026**

## Contexto pedagógico

Esta atividade fecha o ciclo do que a disciplina vem construindo: o aluno já é "inquilino" da infraestrutura — tem seu próprio banco, isolado do dos colegas. Agora é a vez de implementar essa mesma ideia *dentro* da aplicação: usuários diferentes do catálogo de filmes não podem ver os favoritos nem os comentários uns dos outros.

---

## Requisitos — três camadas obrigatórias

### 1. Consumo de API — TMDB

Buscar os filmes com Tom Hanks na API do TMDB (gratuita, com chave de desenvolvedor). Pôster, título e sinopse vêm sempre ao vivo da API — a aplicação **nunca** guarda esses dados nem baixa a imagem, apenas usa a URL que a própria TMDB fornece.

Fluxo de chamadas:

1. `GET /search/person?query=Tom+Hanks` → obtém o `person_id` de Tom Hanks
2. `GET /person/{person_id}/movie_credits` → lista de filmes, cada um com `poster_path`
3. URL final do pôster: `https://image.tmdb.org/t/p/w500{poster_path}` → pronta para uso num `<img>`

### 2. Persistência — MariaDB

Favoritos e comentários são gravados no banco individual do aluno. O catálogo em si **nunca** é salvo — só o que o usuário decide guardar sobre um filme.

Esquema sugerido (adaptável):

```sql
CREATE TABLE usuarios (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(100) NOT NULL,
  email VARCHAR(150) UNIQUE NOT NULL,
  senha_hash VARCHAR(255) NOT NULL,
  criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE favoritos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  usuario_id INT NOT NULL,
  tmdb_movie_id INT NOT NULL,
  titulo VARCHAR(255) NOT NULL,
  poster_path VARCHAR(255),
  criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
  UNIQUE (usuario_id, tmdb_movie_id) -- não deixa favoritar 2x o mesmo filme
);

CREATE TABLE comentarios (
  id INT AUTO_INCREMENT PRIMARY KEY,
  usuario_id INT NOT NULL,
  tmdb_movie_id INT NOT NULL,
  texto TEXT NOT NULL,
  criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);
```

### 3. Segregação de usuário

- A aplicação precisa ter login e cadastro **próprios** (sem relação com login do MySQL ou do Portainer — são usuários do app).
- Toda consulta a favoritos ou comentários precisa ser filtrada pelo usuário logado: `WHERE usuario_id = ?`.
- Nunca retornar dados de outra conta, mesmo que o usuário adivinhe o ID de um favorito alheio (proteção contra IDOR).

---

## Arquitetura de referência

### Como uma ação do usuário atravessa a aplicação

```
Usuário A / Usuário B
        │
        ▼
   Aplicação (sessão → identifica usuario_id de quem pediu)
        │
        ├── buscar filme (Tom Hanks) ──► API TMDB (externa, sem estado) ──► JSON + poster_url
        │
        └── INSERT favorito (usuario_id) / SELECT ... WHERE usuario_id = ? ──► MariaDB do aluno
                                                                                 (linhas usuario_id = A)
                                                                                 (linhas usuario_id = B)
```

- Buscar um filme **nunca grava nada** — é sempre uma chamada direta à TMDB.
- Favoritar ou comentar grava no MariaDB do aluno, sempre vinculado ao `usuario_id` de quem está logado — é esse vínculo que impede o Usuário A de ler o que o Usuário B favoritou.

### Do repositório ao endereço público

```
Repositório GitHub (público, com @siriani no README)
        │  clona e builda a partir do Dockerfile
        ▼
   Portainer do aluno
        │  Deploy the stack
        ▼
   Container (publicado na porta reservada do aluno)
        │  porta vincula o container ao subdomínio pessoal
        ▼
   Subdomínio público
```

O container só aparece publicamente se for publicado exatamente na porta reservada do aluno — é essa porta que vincula o container ao subdomínio pessoal (ver PDF de acessos).

---

## Cenário de uso — teste de ponta a ponta

Cada passo depende do anterior ter funcionado de verdade:

1. Abrir o subdomínio → ver tela de login/cadastro, **não** o catálogo direto.
2. Criar conta nova e fazer login → ver lista de filmes com Tom Hanks (pôster, título, sinopse vindos da TMDB).
3. Favoritar um filme (ex: *Forrest Gump*) e escrever um comentário → recarregar a página → os dois continuam lá.
4. Fazer logout e criar uma segunda conta → **não** ver o favorito nem o comentário deixado na primeira conta.
5. Conferir o repositório no GitHub: público, com Dockerfile, README com `@siriani`, e **nenhuma** senha ou chave de API no código.

---

## Segurança — credenciais só existem do lado do servidor

Como o repositório é público, qualquer chave ou senha que aparecer no código fica exposta assim que houver commit. Isso vale para a chave da API TMDB e para as credenciais do MariaDB.

Regras obrigatórias:

- **Nunca** escrever credenciais direto no código, no Dockerfile, ou em qualquer coisa que rode no navegador do usuário (client-side, incluindo JS de frontend acessível via "Inspecionar elemento").
- Toda chamada à TMDB e ao MariaDB deve partir do **backend**, nunca direto do navegador.
- Configurar credenciais como variáveis de ambiente:
  - No Portainer: campo **Env** ao criar o container (ou um `.env` referenciado no `docker-compose.yml`) para passar a chave da TMDB e os dados de conexão do MariaDB.
  - No repositório: incluir apenas um `.env.example` com os nomes das variáveis (sem valores reais), e adicionar `.env` ao `.gitignore`.

---

## Checklist de avaliação

- [ ] Login e cadastro funcionando de verdade
- [ ] Busca retorna filmes reais da TMDB, com pôster
- [ ] Favoritar e comentar persistem no MariaDB
- [ ] Isolamento comprovado entre duas contas diferentes
- [ ] Container publicado na porta certa, subdomínio no ar
- [ ] Repositório público, organizado, com `@siriani` no README
- [ ] Nenhuma credencial exposta no código ou no frontend
