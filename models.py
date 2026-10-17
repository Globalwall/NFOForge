from dataclasses import dataclass


@dataclass(frozen=True)
class MatchCandidate:
    provider_id: str
    title: str
    year: str | None = None
    studio: str | None = None
    url: str | None = None
    media_type: str = "Scene"
