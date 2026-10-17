import httpx


class JellyfinError(Exception):
    pass


def refresh_library(url: str, api_key: str) -> None:
    endpoint = f"{url.rstrip('/')}/Library/Refresh"
    try:
        response = httpx.post(
            endpoint,
            headers={"X-Emby-Token": api_key},
            timeout=20,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise JellyfinError(f"Jellyfin library refresh failed: {error}") from error
