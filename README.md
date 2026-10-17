# Jellyfin ID-Only NFO Matcher

A small self-hosted web app for scanning video files, finding a manual match in ThePornDB, writing an ID-only NFO, and storing the match in SQLite. A Jellyfin library refresh can be requested after saving.

## Run with Docker Compose

1. Create a `.env` file next to `docker-compose.yml`:

   ```dotenv
   MEDIA_PATH=/path/to/your/media
   THEPORNDB_API_KEY=your_api_key
   JELLYFIN_URL=http://your-jellyfin-host:8096
   JELLYFIN_API_KEY=your_jellyfin_api_key
   ```

   Get a ThePornDB key from [the API tokens page](https://theporndb.net/user/api-tokens). The ThePornDB and Jellyfin keys are optional until their features are used. Keep `.env` private; it is ignored by Git.
2. Run `docker compose up --build`.
3. Open <http://localhost:2026>.

The container mounts the media folder at `/media` and the persistent SQLite database at `./data/matcher.db`. For multiple media roots, change the Compose `MEDIA_ROOTS` value and mount each folder. Roots are separated with semicolons.

## Run with Python

Use Python 3.10 or newer:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:MEDIA_ROOTS = 'D:\Media'
$env:THEPORNDB_API_KEY = 'your_api_key'
uvicorn app:app --reload --port 2026
```

On Windows, separate multiple roots with semicolons. The default root is the `media` folder next to `app.py`. Set `DATABASE_PATH` to change the SQLite database location.

## Workflow

1. The home page scans configured roots for supported video files.
   Use its search field to filter by filename or saved match title; the list is alphabetized.
2. Select a file, adjust its cleaned filename title if needed, and search ThePornDB for both scenes and movies.
3. Choose the correct result to write a sibling `.nfo` file and save/update its SQLite mapping.
4. Check the refresh option to request a Jellyfin library scan. Configure both `JELLYFIN_URL` and `JELLYFIN_API_KEY` to enable it.

The generated NFO contains only `<title>` and `<uniqueid type="ThePornDB">` elements. Its provider ID is path-qualified as `scenes/<id>` or `movies/<id>` to identify the selected ThePornDB media type. Existing sibling NFO files are replaced when a new match is selected.

This MVP has no login. Run it only on a trusted network; anyone who can reach it can scan the configured roots and write NFO files.

## Configuration

| Variable | Purpose |
| --- | --- |
| `MEDIA_ROOTS` | Semicolon-separated media folders the app may scan and write sidecar NFOs into. |
| `DATABASE_PATH` | SQLite database path; defaults to `data/matcher.db`. |
| `THEPORNDB_API_KEY` | ThePornDB API token sent in the `Authorization: Bearer` header. |
| `JELLYFIN_URL` | Base URL for the Jellyfin server, such as `http://jellyfin:8096`. |
| `JELLYFIN_API_KEY` | Jellyfin API key sent as `X-Emby-Token`. |

With Docker Compose, the app is available at `http://localhost:2026` (host port 2026 mapped to container port 8080). For a direct Python run, use `uvicorn app:app --reload --port 2026`. `GET /health` returns `{"status":"ok"}`.

## Tests

Run the standard-library test suite with:

```powershell
python -m unittest discover -s tests
```
# NFOForge
NFOForge scans your media library, matches files to metadata providers, and generates lightweight ID-based NFO files for Jellyfin. Eliminate manual Identify searches, preserve matches across server rebuilds, and let Jellyfin automatically fetch metadata, artwork, cast information, and more.
