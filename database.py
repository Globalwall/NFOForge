import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


def init_db(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY,
                filepath TEXT UNIQUE NOT NULL,
                provider TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()


def get_matches(database_path: Path) -> dict[str, dict[str, Any]]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT filepath, provider, provider_id, title FROM matches"
        ).fetchall()
    return {row["filepath"]: dict(row) for row in rows}


def get_match(database_path: Path, filepath: str) -> dict[str, Any] | None:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT filepath, provider, provider_id, title "
            "FROM matches WHERE filepath = ?",
            (filepath,),
        ).fetchone()
    return dict(row) if row else None


def save_match(
    database_path: Path,
    filepath: str,
    provider: str,
    provider_id: str,
    title: str,
) -> None:
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO matches (filepath, provider, provider_id, title)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(filepath) DO UPDATE SET
                    provider = excluded.provider,
                    provider_id = excluded.provider_id,
                    title = excluded.title,
                    created_at = CURRENT_TIMESTAMP
                """,
                (filepath, provider, provider_id, title),
            )
