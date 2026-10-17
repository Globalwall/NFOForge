import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

import app
import database
from matcher import API_URL, MOVIES_API_URL, ProviderError, ThePornDBClient
from models import MatchCandidate
from nfo import write_nfo
from scanner import clean_title, scan_media


class ScannerTests(unittest.TestCase):
    def test_clean_title_removes_extension_and_release_tags(self):
        self.assertEqual(
            clean_title("Studio.Name - Scene.Title [1080p] x265.mkv"),
            "Studio Name - Scene Title",
        )

    def test_scan_media_finds_supported_video_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "movie.MKV").touch()
            (root / "notes.txt").touch()
            (root / "nested").mkdir()
            (root / "nested" / "clip.mp4").touch()

            self.assertEqual(
                scan_media(root),
                [root / "movie.MKV", root / "nested" / "clip.mp4"],
            )


class PersistenceTests(unittest.TestCase):
    def test_nfo_contains_title_and_provider_id_only(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "clip.mp4"
            video.touch()

            nfo_path = write_nfo(video, "ThePornDB", "scene-123", "Scene Title")
            content = nfo_path.read_text(encoding="utf-8")

            self.assertIn("<title>Scene Title</title>", content)
            self.assertIn(
                '<uniqueid type="ThePornDB" default="true">scene-123</uniqueid>',
                content,
            )
            self.assertNotIn("<plot>", content)

    def test_match_mapping_is_created_and_updated(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "data" / "matcher.db"
            database.init_db(database_path)
            database.save_match(
                database_path, "clip.mp4", "ThePornDB", "old", "Old title"
            )
            database.save_match(
                database_path, "clip.mp4", "ThePornDB", "new", "New title"
            )

            self.assertEqual(
                database.get_match(database_path, "clip.mp4")["provider_id"],
                "new",
            )


class ProviderTests(unittest.TestCase):
    def test_search_uses_theporndb_parse_parameter_and_returns_candidates(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "scene-1",
                            "title": "Example Scene",
                            "date": "2024-05-10",
                            "site": {"name": "Example Studio"},
                        }
                    ]
                },
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            results = ThePornDBClient("test-key", client).search_scenes("Example Scene")

        self.assertEqual(requests[0].url.host, "api.theporndb.net")
        self.assertEqual(requests[0].url.path, "/scenes")
        self.assertEqual(requests[0].url.params["parse"], "Example Scene")
        self.assertEqual(requests[0].headers["authorization"], "Bearer test-key")
        self.assertEqual(results[0].provider_id, "scene-1")
        self.assertEqual(results[0].year, "2024")
        self.assertEqual(results[0].studio, "Example Studio")
        self.assertEqual(results[0].media_type, "Scene")
        self.assertEqual(API_URL, "https://api.theporndb.net/scenes")

    def test_search_includes_movies_and_scenes(self):
        requests = []

        def handler(request):
            requests.append(request)
            media_type = "Movie" if request.url.path == "/movies" else "Scene"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": (
                                "lethalhardcore-stepdaughters-creampied-12"
                                if media_type == "Movie"
                                else "scene-1"
                            ),
                            "title": f"Example {media_type}",
                        }
                    ]
                },
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            results = ThePornDBClient("test-key", client).search("Example")

        self.assertEqual(
            [request.url.path for request in requests], ["/scenes", "/movies"]
        )
        self.assertEqual(
            [request.headers["authorization"] for request in requests],
            ["Bearer test-key", "Bearer test-key"],
        )
        self.assertEqual(
            [candidate.media_type for candidate in results], ["Scene", "Movie"]
        )
        self.assertEqual(
            results[1].url,
            "https://theporndb.net/movies/lethalhardcore-stepdaughters-creampied-12",
        )
        self.assertEqual(MOVIES_API_URL, "https://api.theporndb.net/movies")

    def test_search_rejects_unexpected_response_shape(self):
        with httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"unexpected": []})
            )
        ) as client:
            with self.assertRaisesRegex(ProviderError, "unexpected response format"):
                ThePornDBClient("test-key", client).search_scenes("Example Scene")

    def test_search_wraps_transport_errors(self):
        def handler(_):
            raise httpx.ConnectError("connection failed")

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaisesRegex(ProviderError, "Could not reach ThePornDB"):
                ThePornDBClient("test-key", client).search_scenes("Example Scene")


class AppTests(unittest.TestCase):
    def test_homepage_filters_media_and_lists_files_alphabetically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "media"
            root.mkdir()
            (root / "zebra.mkv").touch()
            (root / "Alpha.mkv").touch()
            database_path = Path(directory) / "matcher.db"

            with (
                patch.object(app, "DATABASE_PATH", database_path),
                patch.dict("os.environ", {"MEDIA_ROOTS": str(root)}, clear=False),
                TestClient(app.app) as client,
            ):
                response = client.get("/")

            self.assertEqual(response.status_code, 200)
            self.assertIn('id="media-filter"', response.text)
            self.assertLess(
                response.text.index("Alpha.mkv"),
                response.text.index("zebra.mkv"),
            )
            self.assertIn("Filter by filename or saved match", response.text)

    def test_search_renders_movie_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "media"
            root.mkdir()
            video = root / "Example.mkv"
            video.touch()
            database_path = Path(directory) / "matcher.db"
            candidate = MatchCandidate(
                provider_id="example-movie",
                title="Example Movie",
                year="2024",
                url="https://theporndb.net/movies/example-movie",
                media_type="Movie",
            )
            environment = {
                "MEDIA_ROOTS": str(root),
                "THEPORNDB_API_KEY": "test-key",
            }

            with (
                patch.object(app, "DATABASE_PATH", database_path),
                patch.dict("os.environ", environment, clear=False),
                patch.object(app, "ThePornDBClient") as provider,
                TestClient(app.app) as client,
            ):
                provider.return_value.search.return_value = [candidate]
                response = client.post(
                    "/search",
                    data={"filepath": str(video), "query": "Example"},
                )

            self.assertEqual(response.status_code, 200)
            self.assertIn("Movie", response.text)
            self.assertIn("Example Movie", response.text)
            self.assertIn(
                "https://theporndb.net/movies/example-movie", response.text
            )
            provider.return_value.search.assert_called_once_with("Example")

    def test_select_writes_scene_nfo_saves_match_and_requests_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "media"
            root.mkdir()
            video = root / "Example Scene.mkv"
            video.touch()
            database_path = Path(directory) / "matcher.db"
            environment = {
                "MEDIA_ROOTS": str(root),
                "JELLYFIN_URL": "http://jellyfin:8096",
                "JELLYFIN_API_KEY": "test-jellyfin-key",
            }

            with (
                patch.object(app, "DATABASE_PATH", database_path),
                patch.dict("os.environ", environment, clear=False),
                patch.object(app.jellyfin, "refresh_library") as refresh,
                TestClient(app.app) as client,
            ):
                response = client.post(
                    "/select",
                    data={
                        "filepath": str(video),
                        "provider_id": "scene-123",
                        "media_type": "Scene",
                        "title": "Example Scene",
                        "refresh": "true",
                    },
                )

            self.assertEqual(response.status_code, 200)
            self.assertIn("Jellyfin library refresh was requested.", response.text)
            refresh.assert_called_once_with(
                "http://jellyfin:8096", "test-jellyfin-key"
            )
            self.assertIn(
                "<title>Example Scene</title>",
                video.with_suffix(".nfo").read_text(encoding="utf-8"),
            )
            self.assertIn(
                '<uniqueid type="ThePornDB" default="true">scenes/scene-123</uniqueid>',
                video.with_suffix(".nfo").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                database.get_match(database_path, str(video))["provider_id"],
                "scene-123",
            )

    def test_select_writes_movie_nfo_with_movies_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "media"
            root.mkdir()
            video = root / "Example Movie.mkv"
            video.touch()

            with (
                patch.dict("os.environ", {"MEDIA_ROOTS": str(root)}, clear=False),
                TestClient(app.app) as client,
            ):
                response = client.post(
                    "/select",
                    data={
                        "filepath": str(video),
                        "provider_id": "movie-123",
                        "media_type": "Movie",
                        "title": "Example Movie",
                    },
                )

            self.assertEqual(response.status_code, 200)
            self.assertIn(
                '<uniqueid type="ThePornDB" default="true">movies/movie-123</uniqueid>',
                video.with_suffix(".nfo").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
