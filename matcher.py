from collections.abc import Sequence

import httpx

from models import MatchCandidate


API_URL = "https://api.theporndb.net/scenes"
MOVIES_API_URL = "https://api.theporndb.net/movies"
PROVIDER = "ThePornDB"


class ProviderError(Exception):
    pass


class ThePornDBClient:
    def __init__(self, api_key: str, client: httpx.Client | None = None):
        self.api_key = api_key.strip()
        self.client = client

    def search_scenes(self, query: str, limit: int = 5) -> list[MatchCandidate]:
        if not self.api_key:
            raise ProviderError(
                "ThePornDB API key is not configured. Set THEPORNDB_API_KEY."
            )

        try:
            if self.client is not None:
                response = self.client.get(
                    API_URL,
                    params={"parse": query},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=20,
                )
            else:
                with httpx.Client() as client:
                    response = client.get(
                        API_URL,
                        params={"parse": query},
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        timeout=20,
                    )
        except httpx.HTTPError as error:
            raise ProviderError(f"Could not reach ThePornDB: {error}") from error
        return self._parse_response(response, limit, "Scene")

    def search_movies(self, query: str, limit: int = 5) -> list[MatchCandidate]:
        if not self.api_key:
            raise ProviderError(
                "ThePornDB API key is not configured. Set THEPORNDB_API_KEY."
            )

        try:
            if self.client is not None:
                response = self.client.get(
                    MOVIES_API_URL,
                    params={"parse": query},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=20,
                )
            else:
                with httpx.Client() as client:
                    response = client.get(
                        MOVIES_API_URL,
                        params={"parse": query},
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        timeout=20,
                    )
        except httpx.HTTPError as error:
            raise ProviderError(f"Could not reach ThePornDB: {error}") from error
        return self._parse_response(response, limit, "Movie")

    def search(self, query: str, limit: int = 5) -> list[MatchCandidate]:
        return self.search_scenes(query, limit) + self.search_movies(query, limit)

    @staticmethod
    def _parse_response(
        response: httpx.Response, limit: int, media_type: str
    ) -> list[MatchCandidate]:
        if response.status_code in (401, 403):
            raise ProviderError(
                "ThePornDB rejected the API key. Check THEPORNDB_API_KEY."
            )
        if response.status_code == 429:
            raise ProviderError("ThePornDB rate limit was reached. Try again shortly.")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise ProviderError(
                f"ThePornDB returned HTTP {response.status_code}."
            ) from error
        try:
            payload = response.json()
        except ValueError as error:
            raise ProviderError("ThePornDB returned an invalid JSON response.") from error

        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ProviderError("ThePornDB returned an unexpected response format.")

        results: Sequence[object] = payload["data"]
        candidates: list[MatchCandidate] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            provider_id = item.get("id")
            title = item.get("title")
            if not provider_id or not title:
                continue
            release_date = str(item.get("date") or item.get("release_date") or "")
            site = item.get("site") or item.get("studio") or {}
            studio = site.get("name") if isinstance(site, dict) else None
            candidates.append(
                MatchCandidate(
                    provider_id=str(provider_id),
                    title=str(title),
                    year=release_date[:4] if len(release_date) >= 4 else None,
                    studio=str(studio) if studio else None,
                    url=f"https://theporndb.net/{media_type.lower()}s/{provider_id}",
                    media_type=media_type,
                )
            )
            if len(candidates) >= limit:
                break
        return candidates
