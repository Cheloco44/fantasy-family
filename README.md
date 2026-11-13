# Redlands Possum Busters

A lightweight public Astro clubhouse for the 2026–27 family ESPN Fantasy NHL league: https://cheloco44.github.io/fantasy-family/ . The owner approved profiles, fictional lore, selected portraits/memes, aggregate league scores, and automatic daily publication targeting **07:00 America/Phoenix**. No paid service is configured.

## What the site shows

- Eight owner-labeled character profiles with separate, visibly fictional league lore. Factual biographies, favorite teams and accomplishments remain empty until supplied.
- Prior-day ESPN team-aggregate recaps, ongoing matchup storylines, a dated archive, current standings/matchup snapshots and visible collection times.
- An approved meme locker with moment/punchline spotlights and combined text/tag/multi-manager filters. The first four family composites illustrate November 11; three original generic demo drawings remain individually labeled.
- Mobile navigation and explicit freshness/coverage warnings. Missing scores are unavailable, not fabricated zeros. Daily rounds are not final weekly matchup results.

Historical player/goalie statistics, active/bench lineup attribution and independently recomputed scoring remain unverified and are not asserted by aggregate recaps. The sample recap route remains clearly sample-only. A successful build or data import is not proof of a deployed refresh: verify the exact Actions run and public page.

## Daily flow

See **[docs/DAILY-FLOW.md](docs/DAILY-FLOW.md)** for the publishing and image-review contract.

Preparation is scheduled for **06:40 Arizona / 13:40 UTC**, with scheduled Pages publication gated until **07:00 Arizona / 14:00 UTC**. GitHub Actions/Pages may be delayed; this is a target, not an exact-time SLA. The workflow is `daily-clubhouse.yml`, separate from the retained manual Pages and diagnostic workflows.

New images require explicit owner approval. No response means approved older art or character portraits, never an unreviewed draft. Dated score memes are not reused as current results for another date. Private drafts and the full reference-image folder stay outside public source and site artifacts. No fresh-scene image-generation provider is configured: this flow works with approved artwork and deterministic score/history-driven text. Newly generated scenes are a separate reviewed step.

Real date-keyed history supports rolling seven-calendar-day jokes. A 'three losses/bye week' roast must identify verified **daily-round** losses and disclose coverage, not pretend they are ESPN weekly W–L or invent an unbroken streak across missing dates.

## Local build and tests

Node 26, pinned Astro/package lock; Python data tools use the standard library.

```bash
npm ci --ignore-scripts --no-fund
python scripts/daily_pipeline.py rebuild
BASE_PATH=/fantasy-family/ ASTRO_TELEMETRY_DISABLED=1 npm run build
npm test
python -m unittest discover -s scripts -p 'test_*.py' -v
npm run dev
```

Development binds to `127.0.0.1`. Builds stay under `~/projects`, not the vault. Set `BASE_PATH=/fantasy-family/` for Pages-compatible paths. No browser request goes to ESPN and no frontend tracking provider is included.

## Content sources

- `src/data/clubhouse.json`: owner-supplied manager/team labels, approved portraits, separate fictional lore and original demo memes. Preserve exact supplied labels; do not invent factual bios or real quotations.
- `src/data/editorial.json`: approved cast mapping, 07:00 target, transparent close/smoked thresholds and approved image catalog.
- `src/data/daily/YYYY-MM-DD.json`: normalized daily aggregate plus a separately timestamped current snapshot. Upsert the same date on corrections, never append duplicates.
- `src/data/recaps.json`: generated editions, score-driven storylines, coverage notes and approved-image choices.
- `src/data/current.json`: current standings and full-matchup totals, not a real-time feed.

Receiving family memes for style learning is not permission to publish the entire collection. Keep draft originals in ignored `private/` or `artifacts/`; export only explicitly approved, metadata-stripped derivatives. New SVG uploads must be sanitized or rasterized; existing demo SVGs were authored locally. Character associations use explicit owner labels, never face identification. Fictional team moms stay unnamed; private personal details and outsiders are not new factual content.

## ESPN and permissions

League `1399646897`, ESPN NHL season `2027`. Authenticated retrieval established `H2H_POINTS`. The November 11 daily totals were independently retrieved as provider aggregates on reviewed run [43326611180](https://github.com/Cheloco44/fantasy-family/actions/runs/43326611180); this is not player/bench reconciliation. See `docs/DAILY-LOOKUP.md`, `docs/CURRENT-DATA.md`, and `docs/ESPN-SETUP.md` for the earlier manual diagnostics.

Keep owner-managed `ESPN_S2`/`ESPN_SWID` only in Actions secrets. These session cookies can grant broader account access even though our client performs fixed read-only GETs. Never paste them in chat or expose them in logs, history, frontend code or artifacts. Public metadata requests have no cookies; credentialed requests refuse redirects and have TLS/size/time bounds. Never upload raw provider/member/owner/player records.

The daily workflow separates collection (repository read, step-scoped ESPN cookies), import/publication (repository write, no ESPN cookies), build (exact published SHA, no ESPN cookies), and Pages deployment (Pages/OIDC permission only). Failed collection or validation preserves last-good data/site; timestamps and stale notices must not claim a failed refresh succeeded. No credentialed workflow runs on pull requests, and no source force-push/rebase or repo visibility/settings change is permitted.

## Publishing, recovery and rollback

Pages source remains **GitHub Actions**, configured by the owner. Manual full refresh: **Actions → Daily clubhouse → Run workflow → main**. Manual runs publish immediately; scheduled runs wait for the morning target. The separate **Deploy public clubhouse** workflow remains a manual, no-ESPN-credentials deployment option for reviewed source.

Before claiming success: inspect the exact run head SHA and job results, read back the remote commit and public page/assets, and verify the edition date and timestamps. Noindex is not access control; this site and approved source are public. The GitHub workflow updates the site, not a Discord family-channel broadcast.

On a failure, inspect sanitized diagnostics rather than printing credentialed logs; repair/review and rerun the same date. On an incorrect release, use an ordinary reviewed revert commit and redeploy—never force-push or portray an old release as current. On an expired ESPN session, have the owner update repository secrets privately.

The gym app, employer infrastructure and real ESPN mutations remain out of scope.
