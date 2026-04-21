"""Pure aggregations for ``music.listening_summary``."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from echo.core.aggregations import daily_distribution, top_n

if TYPE_CHECKING:
    from echo.core.types import Period


def _naive(ts):
    return ts.replace(tzinfo=None) if ts.tzinfo is not None else ts


def build(scrobbles: Iterable, *, period: Period) -> dict[str, Any]:
    """
    Aggregate a pre-filtered iterable of scrobbles into a summary dict.

    A "scrobble" here is any object exposing ``when``, ``artist``, and
    ``track``. That matches the karlicoss/HPI ``my.lastfm`` shape while
    letting tests inject simple dataclasses.
    """
    artists: list[str] = []
    tracks: list[str] = []
    moments = []
    count = 0

    for s in scrobbles:
        count += 1
        a = getattr(s, "artist", "") or ""
        t = getattr(s, "track", "") or ""
        artists.append(a)
        if a and t:
            tracks.append(f"{a} — {t}")
        moments.append(_naive(s.when))

    unique_artists = len({a for a in artists if a})
    unique_tracks = len(set(tracks))

    return {
        "period": period.label or "custom",
        "total_scrobbles": count,
        "unique_artists": unique_artists,
        "unique_tracks": unique_tracks,
        "top_artists": top_n(
            (a for a in artists if a), n=10, key="scrobbles"
        ),
        "top_tracks": top_n(tracks, n=10, key="scrobbles"),
        "daily_distribution": daily_distribution(moments),
        # Deliberately omitted: listening_hours. Last.fm scrobbles do not
        # carry track duration; any estimate would be fabricated.
    }


__all__ = ["build"]
