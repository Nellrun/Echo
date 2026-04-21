"""
Shared fixtures. A thin in-test re-declaration of the Letterboxd domain
classes lets us exercise the aggregation functions without importing
``my.letterboxd`` (which requires the upstream HPI and user config).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class FakeFilm:
    name: str
    year: int | None
    uri: str


@dataclass(frozen=True, slots=True)
class FakeDiary:
    film: FakeFilm
    logged_date: date
    watched_date: date | None = None
    rating: float | None = None
    rewatch: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)
    review: str | None = None


@dataclass(frozen=True, slots=True)
class FakeRating:
    film: FakeFilm
    rating: float
    date: date


@dataclass(frozen=True, slots=True)
class FakeWatchlistItem:
    film: FakeFilm
    date: date


def film(name: str, year: int | None = 2020, slug: str | None = None) -> FakeFilm:
    slug = slug or name.lower().replace(" ", "-")
    return FakeFilm(name=name, year=year, uri=f"https://letterboxd.com/film/{slug}/")
