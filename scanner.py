import os
import re
from pathlib import Path


VIDEO_EXTENSIONS = {
    ".avi",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ts",
    ".webm",
    ".wmv",
}
_BRACKETED = re.compile(r"[\[(].*?[\])]")
_QUALITY_TAGS = re.compile(
    r"\b(?:480p|576p|720p|1080p|1440p|2160p|4k|8k|"
    r"x264|x265|h[._ -]?264|h[._ -]?265|hevc|av1|"
    r"web[._ -]?dl|webrip|bdrip|bluray|hdtv)\b",
    re.IGNORECASE,
)


def clean_title(filename: str) -> str:
    """Strip a video extension and common release tags from a filename."""
    name = Path(filename).stem
    name = _BRACKETED.sub(" ", name)
    name = _QUALITY_TAGS.sub(" ", name)
    name = re.sub(r"[._]+", " ", name)
    return " ".join(name.split()).strip(" -")


def scan_media(root: Path) -> list[Path]:
    """Return supported video files under root, raising on traversal errors."""
    root = root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(f"Media root is not a directory: {root}")

    files: list[Path] = []

    def raise_walk_error(error: OSError) -> None:
        raise error

    for current, _, filenames in os.walk(root, onerror=raise_walk_error):
        for filename in filenames:
            path = Path(current, filename)
            if path.suffix.lower() in VIDEO_EXTENSIONS:
                files.append(path)
    return sorted(files, key=lambda path: str(path).casefold())
