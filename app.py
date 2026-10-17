import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import database
import jellyfin
from matcher import PROVIDER, ProviderError, ThePornDBClient
from nfo import write_nfo
from scanner import VIDEO_EXTENSIONS, clean_title, scan_media


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "matcher.db")))


def configured_media_roots() -> list[Path]:
    raw_roots = os.getenv("MEDIA_ROOTS", str(BASE_DIR / "media"))
    return [Path(root.strip()).expanduser() for root in raw_roots.split(";") if root.strip()]


def resolve_media_file(filepath: str) -> Path:
    try:
        media_path = Path(filepath).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise HTTPException(status_code=404, detail="Media file was not found.") from error

    if not media_path.is_file() or media_path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Select a supported video file.")

    for root in configured_media_roots():
        try:
            resolved_root = root.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if media_path.is_relative_to(resolved_root):
            return media_path
    raise HTTPException(status_code=403, detail="File is outside configured media roots.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.init_db(DATABASE_PATH)
    yield


app = FastAPI(title="Jellyfin NFO Matcher", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    roots = configured_media_roots()
    try:
        files = sorted(
            (file for root in roots for file in scan_media(root)),
            key=lambda file: str(file).casefold(),
        )
    except OSError as error:
        raise HTTPException(status_code=500, detail=f"Could not scan media: {error}") from error
    matches = database.get_matches(DATABASE_PATH)
    return TEMPLATES.TemplateResponse(
        request=request,
        name="index.html",
        context={"files": files, "matches": matches, "roots": roots},
    )


@app.get("/match", response_class=HTMLResponse)
def match_page(request: Request, filepath: str):
    media_path = resolve_media_file(filepath)
    return TEMPLATES.TemplateResponse(
        request=request,
        name="match.html",
        context={
            "filepath": str(media_path),
            "query": clean_title(media_path.name),
            "candidates": [],
            "current_match": database.get_match(DATABASE_PATH, str(media_path)),
            "error": None,
            "message": None,
            "jellyfin_configured": bool(
                os.getenv("JELLYFIN_URL") and os.getenv("JELLYFIN_API_KEY")
            ),
        },
    )


@app.post("/search", response_class=HTMLResponse)
def search(
    request: Request,
    filepath: Annotated[str, Form()],
    query: Annotated[str, Form()],
):
    media_path = resolve_media_file(filepath)
    title_query = query.strip()
    candidates = []
    error = None
    if not title_query:
        error = "Enter a title to search."
    else:
        try:
            candidates = ThePornDBClient(
                os.getenv("THEPORNDB_API_KEY", "")
            ).search(title_query)
        except ProviderError as provider_error:
            error = str(provider_error)
    return TEMPLATES.TemplateResponse(
        request=request,
        name="match.html",
        context={
            "filepath": str(media_path),
            "query": title_query,
            "candidates": candidates,
            "current_match": database.get_match(DATABASE_PATH, str(media_path)),
            "error": error,
            "message": None,
            "jellyfin_configured": bool(
                os.getenv("JELLYFIN_URL") and os.getenv("JELLYFIN_API_KEY")
            ),
        },
    )


@app.post("/select", response_class=HTMLResponse)
def select_match(
    request: Request,
    filepath: Annotated[str, Form()],
    provider_id: Annotated[str, Form()],
    title: Annotated[str, Form()],
    media_type: Annotated[str, Form()],
    refresh: Annotated[bool, Form()] = False,
):
    media_path = resolve_media_file(filepath)
    provider_id = provider_id.strip()
    title = title.strip()
    if not provider_id or not title:
        raise HTTPException(status_code=400, detail="A result with an ID and title is required.")
    media_type_paths = {"Scene": "scenes", "Movie": "movies"}
    media_type_path = media_type_paths.get(media_type)
    if media_type_path is None:
        raise HTTPException(status_code=400, detail="Select a valid ThePornDB media type.")

    nfo_path = write_nfo(
        media_path, PROVIDER, f"{media_type_path}/{provider_id}", title
    )
    database.save_match(DATABASE_PATH, str(media_path), PROVIDER, provider_id, title)
    message = f"Wrote {nfo_path.name} and saved the match."
    jellyfin_url = os.getenv("JELLYFIN_URL", "").strip()
    jellyfin_key = os.getenv("JELLYFIN_API_KEY", "").strip()
    if refresh and jellyfin_url and jellyfin_key:
        try:
            jellyfin.refresh_library(jellyfin_url, jellyfin_key)
            message += " Jellyfin library refresh was requested."
        except jellyfin.JellyfinError as error:
            message += f" {error}"
    elif refresh:
        message += " Jellyfin refresh is not configured."

    return TEMPLATES.TemplateResponse(
        request=request,
        name="match.html",
        context={
            "filepath": str(media_path),
            "query": clean_title(media_path.name),
            "candidates": [],
            "current_match": database.get_match(DATABASE_PATH, str(media_path)),
            "error": None,
            "message": message,
            "jellyfin_configured": bool(jellyfin_url and jellyfin_key),
        },
    )
