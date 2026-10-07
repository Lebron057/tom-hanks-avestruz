// ============================================================
//  P1 — Relatório bimestral de atividades (entrega INDIVIDUAL)
//  ISW055 · Introdução à Computação em Nuvem · Fatec Pompeia · 2026.2
//
//  COMO USAR
//  1. Preencha a seção DADOS DO ALUNO logo abaixo.
//  2. Em cada #atividade(...), preencha "realizada", "situacao" e "url",
//     e escreva o corpo: o que você fez, prints e dificuldades.
//  3. Salve os prints numa pasta "prints/" ao lado deste arquivo e troque
//     `arquivo: none` por `arquivo: "prints/nome-do-print.png"`.
//  4. Compile em https://typst.app (Novo projeto → envie este arquivo e a
//     pasta prints) ou no terminal: typst compile P1_ISW055_template.typ
//  5. Apague os blocos cinza de orientação quando terminar.
//
//  Entrega: 07/10/2026 · PDF nomeado P1_ISW055_Nome_Sobrenome.pdf
// ============================================================

// ---------- DADOS DO ALUNO (edite aqui) ----------
#let aluno = "Iago Amorim Lebron de Lima"
#let turma = "SIST. INTELIGENTES_N"
#let data-relatorio = "07/10/2026"

// ---------- daqui pra baixo, só mexa nas fichas de atividade ----------
#let disciplina = "Introdução à Computação em Nuvem"
#let codigo = "ISW055"
#let professor = "Prof. Allan Lincoln Rodrigues Siriani"
#let accent = rgb("#b96f1f")

#set document(title: "P1 — " + codigo + " — " + aluno, author: aluno)
#set page(paper: "a4", margin: (top: 2.5cm, bottom: 2.5cm, left: 2.5cm, right: 2cm))
#set text(size: 11pt, lang: "pt", region: "BR")
#set par(justify: true, leading: 0.7em)
#set heading(numbering: "1.1")
#show heading.where(level: 1): it => { v(0.6em); text(size: 16pt, it); v(0.2em) }
#show heading.where(level: 2): it => { v(0.5em); text(size: 13pt, it); v(0.1em) }
#show link: set text(fill: accent)
#show figure.caption: set text(size: 9pt, fill: luma(90))
#set table(stroke: 0.5pt + luma(200), inset: 6pt)
#show table: set text(hyphenate: false)
#show table: set par(justify: false)

// ---------- ajudantes ----------
#let orientacao(body) = block(
  width: 100%, fill: luma(245), inset: 9pt, radius: 4pt,
  stroke: (left: 2pt + luma(180)),
  text(size: 9.5pt, fill: luma(90), body),
)

#let evidencia(legenda, arquivo: none) = figure(
  if arquivo == none {
    rect(width: 100%, height: 5.5cm, radius: 4pt, stroke: (paint: luma(170), dash: "dashed"))[
      #align(center + horizon)[
        #text(fill: luma(130), size: 9.5pt)[
          cole o print aqui \
          troque `arquivo: none` por `arquivo: "prints/nome.png"`
        ]
      ]
    ]
  } else {
    image(arquivo, width: 100%)
  },
  kind: image,
  supplement: [Figura],
  caption: legenda,
)

#let registro = state("registro", ())

#let atividade(
  numero, titulo,
  descricao: "",
  planejada: "",
  realizada: "—",
  situacao: "entregue",   // entregue · entregue com atraso · não entregue
  evidencia: "",
  url: "",
  corpo,
) = {
  registro.update(l => l + ((
    numero: numero, titulo: titulo, descricao: descricao,
    planejada: planejada, realizada: realizada, situacao: situacao,
  ),))
  heading(level: 2, [Atividade #numero — #titulo])
  table(
    columns: (3.4cm, 1fr),
    fill: (x, y) => if x == 0 { luma(245) } else { none },
    [*Descrição*], [#descricao],
    [*Data planejada*], [#planejada],
    [*Data realizada*], [#realizada],
    [*Situação*], [#situacao],
    [*Evidência*], [#evidencia],
    [*Link*], [#if url == "" [—] else [#link(url)]],
  )
  corpo
}

// ============================================================
//  CAPA
// ============================================================
#align(center)[
  #v(2.5cm)
  #text(size: 12pt, tracking: 0.12em)[FATEC POMPEIA]
  #v(0.4em)
  #text(size: 10.5pt, fill: luma(110))[#disciplina · #codigo · #turma]
  #v(4.5cm)
  #text(size: 26pt, weight: "bold")[P1]
  #v(0.3em)
  #text(size: 18pt, weight: "bold")[Relatório bimestral de atividades]
  #v(0.8em)
  #text(size: 11pt, fill: luma(110))[Avaliação individual · 2026.2]
  #v(5cm)
  #text(size: 14pt)[#aluno]
  #v(1fr)
  #text(size: 10.5pt)[#professor \ Pompeia, #data-relatorio]
]

#set page(
  numbering: "1",
  number-align: right,
  header: context {
    set text(size: 8pt, fill: luma(120))
    [#codigo · P1 — Relatório bimestral #h(1fr) #aluno]
    line(length: 100%, stroke: 0.4pt + luma(200))
  },
)
#counter(page).update(1)

#outline(title: "Sumário", indent: 1.2em, depth: 2)
#pagebreak()

// ============================================================
= Introdução
// ============================================================
O presente relatório descreve as atividades práticas desenvolvidas ao longo do bimestre na disciplina de Introdução à Computação em Nuvem. O fio condutor da disciplina foi a construção e evolução de um projeto de "Catálogo de Filmes", focado na filmografia do ator Tom Hanks, projetado desde o início para vivenciar os desafios de uma arquitetura moderna e escalável.

Inicialmente, o projeto foi concebido de maneira simplificada, mas rapidamente evoluiu para uma arquitetura baseada em microsserviços. Durante esse processo de transformação, a aplicação passou a ser orquestrada através do Docker, segregando responsabilidades em serviços distintos para autenticação, catálogo e logs. Funcionalidades avançadas foram incorporadas gradualmente, como Controle de Acesso Baseado em Papéis (RBAC), auditoria de eventos utilizando Redis Streams e armazenamento de arquivos de perfil (avatares) na nuvem utilizando o Garage.

O objetivo deste relatório é apresentar de forma técnica e transparente as escolhas arquiteturais realizadas em cada uma das etapas do projeto, demonstrando o funcionamento de cada integração. Nas seções a seguir, cada atividade entregue é detalhada juntamente com suas respectivas evidências de execução e links para o repositório onde o código se encontra versionado.

// ============================================================
= Metodologia
// ============================================================
Todas as atividades foram desenvolvidas de forma contínua no mesmo repositório público do GitHub, integrando um único projeto de catálogo de filmes. O ambiente de desenvolvimento e execução foi orquestrado utilizando Docker e Docker Compose, englobando a stack técnica de Python com FastAPI e Flask, bancos de dados relacionais (MariaDB), cache e mensageria (Redis) e object storage (Garage).

Para assegurar a veracidade das entregas, as datas e horas exatas foram extraídas diretamente do histórico de commits do repositório (`git log`). Os links apresentados nas fichas de atividades apontam para os respectivos commits que representam a conclusão de cada etapa. Os prints registrados demonstram o sistema em pleno funcionamento, além dos artefatos de versionamento exigidos.

// ============================================================
= Quadro de entregas
// ============================================================
#context {
  let l = registro.final()
  table(
    columns: (auto, 1.4fr, 2fr, 2.6cm, 2.9cm, 2.3cm),
    align: (center, left, left, center, center, center),
    fill: (x, y) => if y == 0 { luma(235) } else { none },
    table.header([*Nº*], [*Atividade*], [*Descrição*], [*Data \ planejada*], [*Data \ realizada*], [*Situação*]),
    ..l.map(a => (
      [#a.numero], [#a.titulo], [#text(size: 9pt)[#a.descricao]],
      [#a.planejada], [#a.realizada], [#a.situacao],
    )).flatten()
  )
}

// ============================================================
= Atividades realizadas
// ============================================================
#atividade(
  "1", "Agenda telefônica em Flask",
  descricao: "Nivelamento em sala: sistema monolítico Flask + Jinja com persistência em JSON.",
  planejada: "07/08/2026",
  realizada: "07/08/2026",
  situacao: "entregue",
  evidencia: "Docker Hub — imagem + print da interface",
  url: "https://hub.docker.com/r/lebron057/minha-api-flask",
)[
  *O que foi feito.* Foi desenvolvido um projeto simples de uma agenda telefônica utilizando Flask e Jinja para renderização do frontend. A API possui rotas para listar e cadastrar novos registros (com nome, telefone e valor), persistindo as informações em um arquivo JSON local (`dados.json`). A aplicação foi containerizada utilizando uma imagem leve do Python (`python:3.10-slim`) e a imagem final foi publicada no Docker Hub.

  #evidencia([Atividade 1 — evidência da entrega (link, data e hora visíveis)], arquivo: "prints/atividade1_evidencia.png")
  #evidencia([Atividade 1 — resultado (o sistema funcionando)], arquivo: "prints/atividade1_resultado.png")

  *Dificuldades e como foram resolvidas.* A implementação do código ocorreu de forma tranquila. A maior dificuldade encontrada foi construir o `Dockerfile`, pois foi a minha primeira vez criando um. Isso foi resolvido estudando as instruções básicas (como `FROM`, `WORKDIR`, `COPY`, `RUN`, `EXPOSE` e `CMD`) para configurar adequadamente o ambiente e garantir que o Flask respondesse corretamente dentro do contêiner.
]

#atividade(
  "2", "Catálogo de filmes — Tom Hanks",
  descricao: "Consumo da API TMDB, persistência em MariaDB e segregação por usuário.",
  planejada: "20/08/2026",
  realizada: "20/08/2026 18:17",
  situacao: "entregue",
  evidencia: "GitHub — commit + README + print do catálogo",
  url: "https://github.com/Lebron057/tom-hanks-avestruz/commit/85774b5f66b1a30ccda9b077e6c285f025ab2ab7",
)[
  *O que foi feito.* Foi construída a primeira versão do catálogo de filmes do Tom Hanks utilizando FastAPI e Jinja2. Realizei a integração com a API do TMDB para buscar dados e posters de filmes, e estruturei o banco de dados relacional MariaDB para persistir os usuários e relacioná-los com seus filmes favoritados (segregação por usuário).
  A arquitetura base já previa a orquestração com Docker e Docker Compose, definindo os serviços da aplicação web e do banco de dados na mesma rede, simplificando os testes locais e preparando terreno para os futuros microsserviços.

  #evidencia([Atividade 2 — evidência da entrega (link, data e hora visíveis)], arquivo: "prints/atividade2_evidencia.png")
  #evidencia([Atividade 2 — resultado (o sistema funcionando)], arquivo: "prints/atividade2_resultado.png")

  *Dificuldades e como foram resolvidas.* A principal dificuldade foi entender a estrutura de resposta da API do TMDB e como isolar corretamente o container do MariaDB para garantir a persistência dos dados entre os reinícios dos containers. Isso foi resolvido criando volumes mapeados no `docker-compose.yml`.
]

#atividade(
  "3", "Desacoplando o login — microsserviço de autenticação",
  descricao: "Login, cadastro e esqueci-minha-senha num serviço à parte na rede interna do Docker.",
  planejada: "28/08/2026",
  realizada: "28/08/2026 11:19",
  situacao: "entregue",
  evidencia: "GitHub — commit + docker-compose.yml + print do login funcionando",
  url: "https://github.com/Lebron057/tom-hanks-avestruz/commit/31b256bc52118cf9ca047c6b927ee49ebc6653eb",
)[
  *O que foi feito.* O fluxo de autenticação foi completamente extraído do monólito e isolado num novo microsserviço (`auth-service`). Este serviço, acessível apenas na rede interna do Docker, tornou-se responsável por gerenciar a tabela de usuários, cadastrar, validar credenciais via JWT e oferecer a funcionalidade de recuperação de senha integrada ao Mailtrap.
  O serviço principal (`catalog-service`) passou a atuar como um cliente, repassando as requisições de login e registro para o `auth-service` via HTTP interno, desacoplando a responsabilidade e aprimorando a segurança geral do sistema.

  #evidencia([Atividade 3 — evidência da entrega (link, data e hora visíveis)], arquivo: "prints/atividade3_evidencia.png")
  #evidencia([Atividade 3 — resultado (o sistema funcionando)], arquivo: "prints/atividade3_resultado.png")

  *Dificuldades e como foram resolvidas.* Uma dificuldade notável foi gerenciar os cookies (como `access_token`) a partir das respostas do novo microsserviço de volta para o cliente final passando pelo serviço de catálogo. Isso exigiu atenção extra no repasse correto de headers e cookies de autenticação pelo `catalog-service`.
]

#atividade(
  "4", "Controle de acesso por papel — RBAC",
  descricao: "O campo role passa a decidir permissões reais no backend (403 para usuário comum).",
  planejada: "04/09/2026",
  realizada: "01/09/2026 18:04",
  situacao: "entregue",
  evidencia: "GitHub — commit + print do 403 e da ação de admin",
  url: "https://github.com/Lebron057/tom-hanks-avestruz/commit/a3c1a000c7089e5c7554084497f02d21b2154485",
)[
  *O que foi feito.* Foi implementado o Controle de Acesso Baseado em Papéis (RBAC). Utilizei a abordagem de Enforcement Centralizado (Padrão A), onde a validação e autorização ocorrem diretamente no serviço de borda (`catalog-service`). Este serviço lê as permissões e decide se a ação pode prosseguir (ex: apagar um comentário) dependendo do campo `role` presente no JWT, gerado pelo `auth-service`.
  A lógica adicionada garante que um usuário comum só pode apagar os seus próprios comentários, ao passo que administradores podem excluir qualquer comentário em nome da moderação. Se um usuário não autorizado tenta a operação, o backend devolve adequadamente um erro 403.

  #evidencia([Atividade 4 — evidência da entrega (link, data e hora visíveis)], arquivo: "prints/atividade4_evidencia.png")
  #evidencia([Atividade 4 — resultado (o sistema funcionando)], arquivo: "prints/atividade4_resultado.png")

  *Dificuldades e como foram resolvidas.* A dificuldade foi projetar adequadamente a checagem no endpoint e garantir a correta transmissão do papel (role) de administrador dentro do payload JWT do microsserviço de autenticação, resolvido mapeando o campo corretamente durante a geração do token.
]

#atividade(
  "5", "Logs e auditoria",
  descricao: "Novo log-service com Redis registrando login, ações sensíveis e tentativas negadas.",
  planejada: "25/09/2026",
  realizada: "30/09/2026 16:25",
  situacao: "entregue com atraso",
  evidencia: "GitHub — commit + print da consulta de logs pelo admin",
  url: "https://github.com/Lebron057/tom-hanks-avestruz/commit/1a2c29eb97532bce3aa2f1261d6412985578062e",
)[
  *O que foi feito.* Foi construído um terceiro microsserviço (`log-service`) dedicado à gravação e leitura de trilhas de auditoria das ações do sistema, mantendo a chamada de log como não-bloqueante ("best-effort"). Diversos pontos críticos do backend foram mapeados para emitir eventos de log via HTTP interno.
  Para o armazenamento, foi escolhido utilizar o **Redis Streams (XADD)** em oposição ao Redis List, porque as Streams fornecem naturalmente IDs únicos com timestamps cronológicos nativos, ideal para séries temporais e log de auditoria distribuída. O administrador também conta com um endpoint seguro para visualizar as entradas reversamente.

  #evidencia([Atividade 5 — evidência da entrega (link, data e hora visíveis)], arquivo: "prints/atividade5_evidencia.png")
  #evidencia([Atividade 5 — resultado (o sistema funcionando)], arquivo: "prints/atividade5_resultado.png")

  *Dificuldades e como foram resolvidas.* Foi um desafio configurar o CORS e integrar a interface administrativa com o log-service, pois exigia requisições HTTP enviando corretamente os tokens via Bearer Auth no header, o que foi resolvido repassando a chamada backend-to-backend via `httpx` no serviço de catálogo.
]

#atividade(
  "6", "Upload e perfil de usuário",
  descricao: "Página de perfil com avatar armazenado no Garage (S3); só a referência fica no banco relacional.",
  planejada: "02/10/2026",
  realizada: "30/09/2026 21:07",
  situacao: "entregue",
  evidencia: "GitHub — commit + print do perfil com foto",
  url: "https://github.com/Lebron057/tom-hanks-avestruz/commit/500ef8d21393fb8eef2d7851a2829de8eb507034",
)[
  *O que foi feito.* Desenvolvi a página de perfil público e a funcionalidade de upload de foto de perfil (avatar). Para evitar o armazenamento de binários pesados no banco de dados relacional, utilizei o Garage (object storage compatível com S3) hospedado via contêiner. No MariaDB armazenou-se apenas o caminho/identificador textual da foto gerada, mantendo o banco ágil.
  Em relação ao gerenciamento dos objetos, optei por criar o bucket com **política de leitura pública** (Opção A). Foi a melhor estratégia para simplificar e aliviar o gargalo de processamento das requisições na aplicação, já que avatares são essencialmente dados de visualização abertos dentro da plataforma e não exigem URLs pré-assinadas dinâmicas restritas.

  #evidencia([Atividade 6 — evidência da entrega (link, data e hora visíveis)], arquivo: "prints/atividade6_evidencia.png")
  #evidencia([Atividade 6 — resultado (o sistema funcionando)], arquivo: "prints/atividade6_resultado.png")

  *Dificuldades e como foram resolvidas.* A conexão entre a biblioteca cliente S3 em Python e a estrutura do Garage gerou alguns erros na criação inicial do bucket e definição da política de permissões, que foram devidamente tratados no código adicionando retentativas e configurações adequadas de roteamento no path-style.
]


// ============================================================
= Considerações finais
// ============================================================
O bimestre foi marcado por uma profunda transição conceitual, guiando a implementação de uma arquitetura centralizada (monolítica) para a orquestração distribuída via Docker. Foi imensamente enriquecedor aprender na prática sobre a descentralização do fluxo de autenticação e a necessidade vital da observabilidade através dos eventos de logs, e por fim o armazenamento estático usando object storage.

O maior desafio, indiscutivelmente, residiu na comunicação e propagação segura de tokens (JWT e RBAC) entre contêineres e o manuseio adequado das sessões, assegurando que as regras de negócio fossem aplicadas sempre pelo ponto correto (Padrão A). Para o futuro, pretendo me aprofundar na automatização dos deploys (CI/CD) para garantir a estabilidade sempre que um novo componente for adicionado à rede.

// ============================================================
= Declaração de autoria
// ============================================================
Declaro que este relatório foi elaborado por mim, individualmente, e que as evidências apresentadas correspondem a entregas de minha autoria, verificáveis nos links informados. Nas atividades realizadas em grupo, o conteúdo aqui descrito refere-se à minha participação.

#v(1.5cm)
#grid(
  columns: (1fr, 1fr), gutter: 2cm,
  align(center)[#line(length: 100%, stroke: 0.5pt) \ Iago Amorim Lebron de Lima],
  align(center)[#line(length: 100%, stroke: 0.5pt) \ Pompeia, 07/10/2026],
)
