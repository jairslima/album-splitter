"""
Busca tracklist de álbuns no MusicBrainz (sem chave de API).
Retorna lista de (titulo, duracao_segundos).
"""

import requests
import time

_API = "https://musicbrainz.org/ws/2"
_HEADERS = {"User-Agent": "AlbumSplitter/1.0 (personal use)"}


def _get(url, params):
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def search_releases(artist: str, album: str) -> list[dict]:
    """Retorna lista de releases encontrados (id, title, artist, date, track_count)."""
    query = f'artist:"{artist}" AND release:"{album}"'
    data = _get(f"{_API}/release/", {"query": query, "fmt": "json", "limit": 8})
    results = []
    for r in data.get("releases", []):
        results.append({
            "id": r["id"],
            "title": r.get("title", ""),
            "artist": r.get("artist-credit", [{}])[0].get("artist", {}).get("name", ""),
            "date": r.get("date", ""),
            "track_count": r.get("track-count", 0),
        })
    return results


def get_tracklist(mbid: str) -> list[tuple[str, int]]:
    """
    Dado o MBID de um release, retorna lista de (titulo, duracao_segundos).
    Duração 0 se indisponível.
    """
    time.sleep(1.1)  # respeita rate limit do MusicBrainz (1 req/s)
    data = _get(f"{_API}/release/{mbid}", {"inc": "recordings", "fmt": "json"})
    tracks = []
    for medium in data.get("media", []):
        for t in medium.get("tracks", []):
            title = t.get("title") or t.get("recording", {}).get("title", "")
            ms = t.get("length") or t.get("recording", {}).get("length") or 0
            tracks.append((title, ms // 1000))
    return tracks


def auto_search(artist: str, album: str) -> list[tuple[str, int]]:
    """Atalho: busca e retorna o primeiro resultado com faixas."""
    releases = search_releases(artist, album)
    if not releases:
        return []
    return get_tracklist(releases[0]["id"])
