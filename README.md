# Echo

> **Your personal data, answerable by Claude.**
> An MCP server that turns your Letterboxd, Last.fm, Trakt, ps-timetracker
> and other exports into tools an LLM can call — locally, offline, under
> your control.

Echo is a [Model Context Protocol](https://modelcontextprotocol.io) server
that sits on top of [karlicoss/HPI](https://github.com/karlicoss/HPI) and
exposes your own digital life to assistants like **Claude Desktop**.
Instead of giving the model a pile of CSV rows, Echo gives it **insight
tools** — precomputed summaries, taste profiles, and a cross-source
activity timeline — that fit into a prompt and produce genuinely good
answers.

**Keywords:** MCP server, Claude Desktop, personal data, quantified self,
Letterboxd, Last.fm, Trakt, lifelogging, HPI, Human Programming Interface,
self-hosted AI, LLM tools.

---

## What you can ask after plugging it in

```
You: What did I watch last quarter and how did I rate it?
Claude: (calls films.watched_summary period="2026-Q1")
        You logged 38 films in Q1 2026, averaged 3.6★.
        Your top picks were Perfect Days (5★), Anatomy of a Fall (4.5★)…
```

```
You: Am I in a new music phase, or just re-listening to old stuff?
Claude: (calls music.taste_profile)
        Core artists (stable long-term + last 30 days): Radiohead, Mitski.
        Flings (only last month): Yves Tumor, Mk.gee — no long-term history.
```

```
You: Find everything I did around the week I watched Dune 2.
Claude: (calls query.film title="Dune: Part Two" → gets date)
        (calls cross.activity_timeline period="2026-03-08..2026-03-15")
        That week you logged 3 films, scrobbled ~400 tracks (top: Jónsi)…
```

No rows. No pagination. No 40k-token prompt. Just answers.

---

## Why it exists

Most "chat with my data" tools either:

1. Hand the LLM raw rows and run out of context by row 50, **or**
2. Translate questions to SQL — which works for a database but fights back
   on messy, long-tail personal data where the *right aggregation* is
   rarely what the model guesses first.

Echo takes a third path: **opinionated, precomputed aggregations** that
the LLM picks from a menu. Adding a new domain means adding a new menu
item, not teaching the model a new query language.

---

## Features

- **Insight-first tools.** Domain-specific summaries (`films.watched_summary`,
  `music.listening_summary`, `*.taste_profile`) that fit comfortably in a
  single LLM turn.
- **Cross-domain timeline.** `cross.activity_timeline` merges every
  configured source into one sorted feed; dense sources like scrobbles are
  automatically collapsed into daily summaries so you can scan months at
  a glance.
- **Flexible periods.** Tools accept
  `last_week` / `last_month` / `last_year` / `2026` / `2026-04` /
  `2026-Q1` / `2026-01-01..2026-03-31` / `all`.
- **Bounded escape hatch.** `query.scrobbles`, `query.diary`, `query.film`
  for the rare cases when the model really does want a raw row — always
  with mandatory date filters and hard result caps (200 / 100 / 1).
- **Pluggable providers.** Adding Trakt, Spotify, GitHub, or your own
  source is one directory and one registry line.
- **Local, offline, read-only.** Zero network calls. Zero writes. Stateless
  between tool calls. Your data stays on your disk.

## How it works

Echo is the **third layer** of a small three-part stack. Each layer has
one job.

```
  raw exports              typed Python              MCP tools
 (zips, JSONs, CSVs) ───▶  (my.letterboxd,    ───▶  (films.*, music.*,
  hpi-harvester             my.lastfm, ...)         cross.*, query.*)
                            hpi-modules             echo  ← this repo
```

| Layer                                                           | Repo                                                              | What it does                                                     |
| --------------------------------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------- |
| 1. Harvester                                                    | [`hpi-harvester`](https://github.com/nellrun/hpi-harvester)       | downloads and snapshots raw exports                              |
| 2. Modules                                                      | [`hpi-modules`](https://github.com/nellrun/hpi-modules)           | turns raw files into typed objects (`my.letterboxd.diary()`…)    |
| 3. **Echo**                                                     | this repo                                                         | exposes those objects to LLMs over MCP                           |

Echo imports only from `my.*`. It never parses files, never holds state
between calls, and never writes. Swap out the sources underneath and
everything keeps working.

## Shipping tools

### Films — powered by `my.letterboxd`

| Tool                                    | Returns                                                                                          |
| --------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `films.watched_summary(period)`         | count, rewatches, avg rating, rating distribution, top-rated, most-watched, daily distribution   |
| `films.taste_profile()`                 | favourite decades (by count + avg rating), most-rewatched, global rating distribution            |
| `films.watchlist_overview()`            | total queued, release-decade mix, 10 most recent, 5 longest-pending additions                    |

> *Director-level preferences and Letterboxd-average comparisons aren't
> in the export. Add a scraper/TMDB provider if you want them.*

### Shows — powered by `my.trakt`

| Tool                                    | Returns                                                                                          |
| --------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `shows.watched_summary(period)`         | total plays, episodes / movies played, distinct shows & episodes, top shows, most-watched movies, daily distribution |
| `shows.taste_profile()`                 | most-watched shows, most-rewatched movies, favourite release decades, rating distribution       |
| `shows.watchlist_overview()`            | total queued, show vs movie split, release-decade mix, 10 most recent, 5 longest-pending         |

> *Trakt covers both TV and films. `shows.*` uses Trakt's combined
> history; `films.*` stays on Letterboxd diary entries. They're
> complementary, not redundant.*

### Music — powered by `my.lastfm`

| Tool                                    | Returns                                                                                           |
| --------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `music.listening_summary(period)`       | total scrobbles, unique artists/tracks, top artists, top tracks, daily distribution               |
| `music.taste_profile()`                 | top artists long-term vs last 30 days, **core** set (stable) and **flings** set (new-only)        |

> *No `listening_hours` field — Last.fm scrobbles don't carry duration;
> any estimate would be fabricated.*

### Gaming — powered by `my.ps_timetracker`

| Tool                                    | Returns                                                                                           |
| --------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `gaming.play_summary(period)`           | total sessions, total hours, unique games, top games by hours, platform mix, daily distribution   |
| `gaming.taste_profile()`                | top games long-term vs last 30 days (by hours), **core** set (stable) and **flings** set (new-only) |
| `gaming.library_overview()`             | library snapshot: total games, total hours, platform mix, top 10 by hours, 10 most-recently-played |

> *ps-timetracker is friend-presence based — sessions are wall-clock
> durations observed from outside, so they can be shorter than true play
> time if presence pings were missed. Ranking is by hours, not session
> count: a single long evening with one game outweighs many quick hops.
> No "watchlist" analogue here — the source only exposes games already
> seen, not queued titles.*

### Cross-domain

| Tool                                       | Returns                                                                        |
| ------------------------------------------ | ------------------------------------------------------------------------------ |
| `cross.activity_timeline(period, sources?)`| merged chronological feed. Music is collapsed to one daily summary per day.    |

### Query escape hatch (bounded)

| Tool                                                           | Purpose                                                                              | Hard cap |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------ | -------- |
| `query.scrobbles(from_date, to_date, artist?, track?, limit?)` | raw scrobbles in a date window                                                       | 200      |
| `query.diary(from_date, to_date, min_rating?, limit?)`         | raw diary entries in a date window                                                   | 100      |
| `query.watchlist(limit?, added_after?)`                        | raw watchlist entries, newest first                                                  | 200      |
| `query.film(title? | letterboxd_uri?)`                         | one film + every time you watched it + current rating + watchlist flag + per-watch reviews/tags | 1 film   |
| `query.film_search(query, limit?)`                             | "have I seen this?" — fuzzy substring lookup across diary, ratings, and watchlist    | 50       |
| `query.artist(name, top_tracks?)`                              | "have I listened to this artist?" — substring over scrobbles with play stats         | —        |
| `query.album(album, artist?, top_tracks?)`                     | "have I listened to this album?" — substring on album, optional exact-artist filter  | —        |
| `query.trakt_history(from?, to?, media_type?, show?, limit?)`  | raw Trakt watch history, newest first — filter by date window, episode vs movie, or exact show | 200 |
| `query.show(title)`                                            | one show + all episodes watched + show / episode ratings + watchlist flag            | 1 show   |
| `query.trakt_watchlist(media_type?, added_after?, limit?)`     | raw Trakt watchlist (shows + movies), newest first                                   | 200      |
| `query.gaming_sessions(from_date, to_date, game?, platform?, limit?)` | raw ps-timetracker sessions in a date window                                  | 200      |
| `query.game(title)`                                            | one game — session totals across history plus library snapshot stats                 | —        |

---

## Quick start

### 1. Clone the repos side-by-side

```bash
git clone https://github.com/nellrun/hpi-modules.git
git clone https://github.com/nellrun/echo.git
```

### 2. Install with pipx (recommended)

[`pipx`](https://pipx.pypa.io) gives Echo its own isolated venv and puts
the `echo-mcp` command on your `PATH`. Because `hpi-modules` is not on
PyPI, we install it into Echo's venv via `pipx inject`.

```bash
# Capture absolute paths to both clones so later `cd` doesn't break things.
# Run this from the directory where you just cloned the two repos.
export ECHO_DIR="$PWD/echo"
export HPI_MODULES_DIR="$PWD/hpi-modules"

# 1) install Echo (creates an isolated venv, adds `echo-mcp` to PATH)
pipx install --editable "$ECHO_DIR"

# 2) inject hpi-modules so Echo can import my.letterboxd / my.lastfm.
#    `pipx inject <app>` treats its first argument as a package name, but
#    on case-insensitive filesystems (macOS default) it refuses if a folder
#    called `echo` / `Echo` exists in cwd. `cd ~` sidesteps the collision.
cd ~
pipx inject echo --editable "$HPI_MODULES_DIR"

# sanity check
which echo-mcp
```

Why this dance? `pipx install -e ./echo` fails on its own because Echo
depends on `hpi-modules`, which lives in a sibling repo and isn't on
PyPI — pipx's resolver can't find it. `pipx inject` sidesteps the
resolver and drops a local editable install straight into the venv.

> **Using plain `pip` instead?** In a virtualenv:
> `pip install -e ./hpi-modules && pip install -e ./echo` works fine —
> a single venv sees both editable installs, and there's no
> case-sensitivity trap.

### 3. Point `my.*` at your exports

Create `~/.config/my/my/config/__init__.py`:

```python
class letterboxd:
    # Download from https://letterboxd.com/settings/data/
    export_path = '~/data/letterboxd/letterboxd-*.zip'

class lastfm:
    # See https://github.com/karlicoss/HPI/blob/master/doc/MODULES.org#mylastfm
    export_path = '~/data/lastfm/scrobbles.json'

class trakt:
    # Trakt snapshots produced by hpi-harvester (one JSON per pull).
    export_path = '~/data/trakt/*.json'

class ps_timetracker:
    # ps-timetracker snapshots produced by hpi-harvester.
    export_path = '~/data/ps_timetracker/*'
```

Verify the data pipeline before touching Claude:

```bash
hpi doctor my.letterboxd
hpi doctor my.lastfm
hpi doctor my.trakt.all
hpi doctor my.ps_timetracker.all
```

### 4. Plug into Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or the Windows equivalent:

```json
{
  "mcpServers": {
    "echo": {
      "command": "echo-mcp"
    }
  }
}
```

Restart Claude Desktop. You should see the `films.*`, `music.*`,
`shows.*`, `gaming.*`, `cross.*` and `query.*` tools appear in the tool
picker. Ask it something.

### 5. (Optional) Debug with mcp-inspector

```bash
echo-mcp   # runs the stdio MCP loop directly; pair with mcp-inspector to poke at tools
```

### Upgrading

```bash
git -C "$ECHO_DIR" pull          # editable install picks up the changes automatically
git -C "$HPI_MODULES_DIR" pull
```

No reinstall needed — both packages are `--editable`.

## Adding your own data source

A provider is a single directory. Create
`src/echo/providers/<source>/__init__.py` with:

```python
class MyProvider:
    name = "myservice"

    def is_available(self) -> bool:
        # check that my.<yourmodule> is configured
        ...

    def events(self, period):
        # yield Event(timestamp, source, kind, title, payload)
        # powers cross.activity_timeline for free
        ...

    def register_tools(self, mcp):
        # @mcp.tool() wrappers for domain-specific insights
        ...
```

Add one line in `server.py` to register it, and you're done. Cross-domain
tools pick it up automatically.

## Design principles

- **Aggregations beat pagination.** If an LLM needs every row to answer a
  question, the tool is the wrong shape.
- **Be honest about coverage.** If a signal can't be computed from the
  data at hand, skip the field and say so in a `coverage_note` — don't
  hallucinate a plausible-looking number.
- **Stateless server.** No sessions, no conversation memory, no caches at
  the Echo layer. Caching belongs in `my.*` via `cachew` where it can key
  on input file hashes.
- **Provider boundary is the only extension point.** Don't teach `cross.*`
  about music; teach music to emit `Event`s.

## Status

Alpha. Four providers shipping (Letterboxd, Last.fm, Trakt,
ps-timetracker), 191 tests green, FastMCP bootstrap in place. Things
that will probably change:

- Tool naming convention (underscore vs dot) once MCP clients settle.
- Shape of `taste_profile` responses as real conversations reveal gaps.
- A proper `hpi doctor`-style `echo doctor` command for debugging.

Roadmap: GitHub (commits/PRs), Spotify (wrapped-style yearly views),
a `timeline_summarise` tool that condenses a long window into a few
sentences.

## Development

```bash
pip install -e ".[tests,dev]"
pytest                       # 191 tests, runs in <0.2s
ruff check src tests
mypy src
```

## Related projects

- [karlicoss/HPI](https://github.com/karlicoss/HPI) — the upstream "HPI"
  project Echo builds on. If you want raw Python access to your data,
  start there.
- [Model Context Protocol](https://modelcontextprotocol.io) — the
  standard Echo speaks.
- [FastMCP](https://github.com/jlowin/fastmcp) — the Python framework
  used under the hood.

## License

MIT — see [LICENSE](LICENSE).
