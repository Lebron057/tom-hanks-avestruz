import os
import httpx

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


def _get_api_key() -> str:
    return os.getenv("TMDB_API_KEY", "")


async def get_tom_hanks_movies() -> list[dict]:
    """
    Busca filmes com Tom Hanks na API TMDB.
    1. Pesquisa pelo person_id de Tom Hanks
    2. Busca os créditos de filmes dele
    3. Retorna lista de dicts com id, title, overview, poster_url
    """
    api_key = _get_api_key()
    headers = {
        "accept": "application/json",
    }
    params_base = {"api_key": api_key, "language": "pt-BR"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Buscar person_id do Tom Hanks
        resp = await client.get(
            f"{TMDB_BASE_URL}/search/person",
            params={**params_base, "query": "Tom Hanks"},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("results"):
            return []

        person_id = data["results"][0]["id"]

        # 2. Buscar créditos de filmes
        resp = await client.get(
            f"{TMDB_BASE_URL}/person/{person_id}/movie_credits",
            params=params_base,
            headers=headers,
        )
        resp.raise_for_status()
        credits = resp.json()

    # 3. Montar lista de filmes
    movies = []
    seen_ids = set()

    for movie in credits.get("cast", []):
        tmdb_id = movie.get("id")
        if tmdb_id in seen_ids:
            continue
        seen_ids.add(tmdb_id)

        poster_path = movie.get("poster_path")
        movies.append({
            "id": tmdb_id,
            "title": movie.get("title", "Sem título"),
            "overview": movie.get("overview", "Sinopse não disponível."),
            "poster_url": f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None,
            "release_date": movie.get("release_date", ""),
        })

    # Ordenar por data de lançamento (mais recente primeiro)
    movies.sort(key=lambda m: m.get("release_date", "") or "", reverse=True)
    return movies
