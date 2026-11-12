# Redlands Possum Busters

A lightweight Astro clubhouse for the 2026–27 family ESPN Fantasy NHL league. Public launch approved by Marcelo at `https://cheloco44.github.io/fantasy-family/`. A successful deployment and URL read-back are required before calling it live.

## What's implemented

- Thirteen static routes: dashboard, eight individual manager profiles, manager directory, meme locker, recap archive and sample recap.
- Eight owner-supplied team/manager labels and explicitly labeled portraits. Optimized 400×400 WebP derivatives, no image EXIF. Original contact sheet and reference manifest stay ignored under `private/`.
- Three original generic demo memes, combined caption/tag/manager filters, honest empty states and reset. No generic demo meme is attributed to an actual manager.
- Mobile navigation, explicit results-unavailable status, and no external frontend tracking resources.
- Read-only ESPN settings probe and separate manual-only GitHub Actions access check. Authenticated settings access was verified on run43227217052; this does not establish scoring or historical-lineup correctness.

## What's NOT implemented

Authenticated current collection succeeded on run `43273159316`: ESPN reported head-to-head points, eight teams and four matchups. The source snapshot is an exact copy of that normalized artifact; its display still requires the reviewed Pages release and URL read-back. ESPN team-ID-to-manager mapping, historical active/bench attribution, accurate daily recaps, correction replay, and the05:00 America/Phoenix automatic refresh remain unimplemented/unverified. Sample recaps are not real results. Biographies, favorite NHL teams, achievements and approved scouting reports remain empty.

## Run locally

Node26 and npm are used by the launch workflow; Astro is pinned in package-lock.json. Python tools use the standard library.

```sh
npm ci --ignore-scripts
ASTRO_TELEMETRY_DISABLED=1 npm run build
npm test
python3 -m unittest discover -s scripts -p 'test_*.py' -v
npm run dev
```

The dev server binds to127.0.0.1 only. `npm run preview` serves the static build. For a build matching Pages:

```sh
BASE_PATH=/fantasy-family/ ASTRO_TELEMETRY_DISABLED=1 npm run build
npm test
```

## Publish the approved site

Pages must be enabled by the owner with **Settings → Pages → Source: GitHub Actions**. No personal-token Pages administration permission is needed when the owner configures it directly.

After reviewed source is fast-forwarded to main, run **Actions → Deploy public clubhouse → Run workflow → main**. The workflow is manual-only, pins all actions to full verified commit hashes, builds with `/fantasy-family/`, runs tests and uploads only `dist/`. Only the deploy job gets `pages: write` and `id-token: write`; the build gets no ESPN credentials. No push trigger or daily schedule is enabled.

Verify the exact run head SHA, all jobs and the public site before saying deployment succeeded. URL: https://cheloco44.github.io/fantasy-family/ . This is public; noindex is not privacy or authentication. No paid service has been approved.

## Fictional league lore

The owner supplied eight playful storylines and confirmed The Juice is rich and The Commissioner is Marcelo. Store these in `loreTitle`, `loreText`, and `loreKind`, separate from factual `bio`, favorite teams and verified ESPN data. Both the manager directory and individual pages disclose fiction/exaggerated banter. No narrative quote is presented as a real statement by a family member. Robert’s approved public story focuses on roster churn and league rivalry. Do not use these fictional anecdotes as evidence for performance recaps.

## Edit profiles and memes

`src/data/clubhouse.json` is the content source. Preserve supplied display names/team names unless corrected by the owner. Profile `approved` is an editorial record, not a security boundary. Do not invent bios, awards, favorite teams or quotes.

- Portraits: place only approved, metadata-stripped derivatives under `public/avatars/` and update the record's relative `image` path. Do not upload original photos/contact sheets/private manifests.
- Biographies: accept self-written approved text; Astro escapes text, so don't add raw HTML sinks.
- Memes: add approved static PNG/JPG/WebP/GIF files to `public/memes/`, with unique id, caption, contributor nickname, ISO date, tags, optional manager slug and exactly one featured item. Strip EXIF and confirm rights/consent. Untrusted SVG files must be sanitized or converted; current SVG artwork was authored locally.
- Search matches captions; tag and manager filters combine. `manager: null` means unassigned, not an implied person. The gallery works without JavaScript, though filtering needs it.
- Keep headshots, character references and memes distinct. Receiving an image isn't approval to publish the whole collection. The47-image vault folder is not copied into this repo.

## Current standings and matchup snapshots

The owner approved public ESPN team names, standings and current matchup scores. A separate manual collector workflow exports an allowlisted snapshot without account/member details. It does not alter lineups, trades or transactions. See `docs/CURRENT-DATA.md`. The current-data file is separate from fictional lore and sample recaps.

The website shows a manual snapshot timestamp in America/Phoenix and dynamically warns once it is 24 hours old. No real-time or automatic-refresh claim is made. Scores are full-matchup totals, never yesterday’s contribution. Category W–L–T is not fantasy points. Missing scores are unavailable, not fabricated zeros; missing ranks are not invented. Profile links wait for verified ESPN team-ID mappings.

Failed collection must leave the last successful snapshot untouched. The collector does not commit source or deploy; after a successful run the exact sanitized artifact must be checked before importing and manually deploying. No credentialed job runs on pull requests.

## ESPN setup and next gates

See `docs/ESPN-SETUP.md`. Never paste cookies in chat or put them in files/history/build outputs. Session cookies may grant account-wide access even though the client performs only a fixed GET. Use Actions secrets only in the separate read-only probe and collection workflows. Never pass them to the public site build.

Before live recaps: validate actual points/category rules, scoring vs matchup periods, historical lineups, date/game mapping and goalie constraints. Compare a completed date against ESPN. Test off-days, postponements, missing results, weighted ratios, correction replay, duplicate-date prevention and failure preservation. Store only approved allowlisted public fields; never ship raw provider payloads or member records.

Yesterday must use America/Phoenix calendar boundaries; `src/lib/clock.mjs` covers that small piece. A future daily cron target would be12:00 UTC, but GitHub scheduling can be delayed. Nothing currently refreshes scores automatically.

## Troubleshooting and rollback

- Blank styles/broken assets: verify BASE_PATH and the exact Pages project URL.
- Deployment403: check Pages source and the workflow's built-in token permissions; don't print tokens or broaden personal-token access blindly.
- Results unavailable: expected until real data integration is implemented. The successful access probe is not a results refresh.
- Failed build/deploy: inspect the exact noncredentialed deployment run. Keep the last published site; do not publish a partial output directory.
- Rollback after a problematic release: restore a previously reviewed revision via a normal revert commit on main and manually deploy that reviewed revert. Never force-push; never rerun an old release while claiming it contains current changes.

The gym app is out of scope. No real transactions, trades or lineup mutations are permitted.
