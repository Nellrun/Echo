"""Regression tests for the music provider's HPI adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from echo.providers.music import _normalise


@dataclass
class HPIScrobble:
    """Shape of ``my.lastfm``'s Scrobble: ``dt`` / ``artist`` / ``name`` / ``album``."""

    dt: datetime
    artist: str
    name: str
    album: str | None = None


@dataclass
class LegacyScrobble:
    """Older/alternative shape some dumps expose: ``when`` / ``track``."""

    when: datetime
    artist: str
    track: str
    album: str | None = None


def test_normalise_maps_dt_to_when() -> None:
    ts = datetime(2026, 2, 1, 12, tzinfo=timezone.utc)
    out = _normalise(HPIScrobble(dt=ts, artist="A", name="song"))
    assert out.when == ts
    assert out.track == "song"
    assert out.artist == "A"


def test_normalise_accepts_legacy_when_and_track_fields() -> None:
    ts = datetime(2026, 2, 1, 12)
    out = _normalise(LegacyScrobble(when=ts, artist="A", track="song"))
    assert out.when == ts
    assert out.track == "song"


def test_normalise_coerces_missing_strings_to_empty() -> None:
    @dataclass
    class Sparse:
        dt: datetime
        artist: str | None = None
        name: str | None = None

    out = _normalise(Sparse(dt=datetime(2026, 2, 1)))
    assert out.artist == ""
    assert out.track == ""
    assert out.album is None


def test_normalise_passes_album_through() -> None:
    out = _normalise(
        HPIScrobble(dt=datetime(2026, 2, 1), artist="A", name="s", album="Kid A")
    )
    assert out.album == "Kid A"
