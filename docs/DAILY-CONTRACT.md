# Daily clubhouse implementation contract

Owner authorization: daily website update targeting **07:00 America/Phoenix**, prior Arizona calendar day; automatic reviewed collection/publication now approved. New images require owner review, no-response fallback to approved existing assets. The owner approved the prior Nov11 recap, four meme composites and four lore edits. No paid generation, accounts, outside infrastructure or gym changes. Existing AGENTS remains unchanged (protected); this latest direct owner instruction supersedes its older no-schedule scope for this feature only.

## Shared file/CLI contracts

Parent owns this document, docs/DAILY-FLOW.md, `src/data/editorial.json`, approved image copies, seeded daily bundle. Never modify another worker's files.

Backend owns `scripts/daily_pipeline.py`, `scripts/test_daily_pipeline.py`, generated `src/data/recaps.json`. Standard library only. CLI:
- `python scripts/daily_pipeline.py collect --network --output-dir artifacts/daily-batch [--date YYYY-MM-DD]` fixed league/season, defaults yesterday AZ. Writes EXACT `daily.json`, `current.json`; both normalized/secret checked, no raw account/member/player data. No source changes in collect mode.
- `python scripts/daily_pipeline.py import --input-dir artifacts/daily-batch` validates complete artifact AGAIN, atomically upserts `src/data/daily/DATE.json` as `{daily: ..., current: ...}`, replaces global `src/data/current.json` with imported current snapshot (not older than last good), rebuilds `src/data/recaps.json`. No network or secrets for import. Idempotent date keys, corrections recompute history/trends. Unchanged/invalid input preserves last good source. Stage all outputs only after validation.
- `python scripts/daily_pipeline.py rebuild` generates recaps from existing sanitized archived bundles and approved editorial catalog, offline.
Existing scripts/lookup_daily.py and collect_current.py MUST remain untouched; import helpers if useful. Keep previous 42 Python tests passing.

`src/data/editorial.json`: schemaVersion1, timezone, publishTarget07:00, closeMargin5, smokedMargin20, cast mapping strings ESPN team IDs to {slug,displayName,teamName?} (optional polished teamName is presentation-only), approvedMemes array. Each meme has id,image,caption,date,managers:[slugs],tags:[...],approvalStatus:'approved',contextType:'dated'|'evergreen'. Only approved assets are candidates. Dated assets can illustrate that date only in recap; locker labels archive dates. Evergreen/approved avatar is the fallback for other dates; no unapproved drafts in public source/site/artifact. No image generation or paid provider is configured: future images are manually prepared/reviewed; scheduled run never waits for them.

Archive daily schema: preserve known lookup fields schemaVersion/source/dataKind/date/timeZone/fetchedAt/leagueId/seasonId/scoringType/scoringPeriodId/matchupPeriodId/periodEvidence/teams. ADD `sourceRunUrl` (null or the fixed repository's public Actions run URL), `status` ('verified-aggregate','incomplete','off-day'), `matchups` list [{id,homeId,awayId}] so trend comparisons use actual opponents. Per-team exact keys id,name,dailyPoints,available,pointSource. periodEvidence exact gameCount,allGamesStatsOfficial. Current schema unchanged from collect_current.py. Off-day means no scheduled games found in complete public pro schedule for the date; DO NOT invent zero points or daily wins: dailyPoints null, status off-day, scoringPeriodId/matchupPeriodId may null, matchups empty. Incomplete/provisional data may be reported as such but earns no final daily W/L trends.

Generated recaps schema: {schemaVersion:1,timezone:'America/Phoenix',publishTarget:'07:00',editions:[...]}. Newest first. Each edition EXACT shared UI fields:
- date, sourceFetchedAt, sourceRunUrl (public Actions run when known, else null), scoringPeriodId, matchupPeriodId, status ('verified-aggregate','incomplete','off-day'), headline, dek, coverageNote, weeklyContextAt (ISO string or null), matchups:[]
- Each matchup: id, homeId, awayId, homeAlias, awayAlias, homePoints (number|null), awayPoints, margin(number|null), classification ('close','smoked','standard','tie','unavailable'), title, story, trendNotes:string[], weeklySummary:string|null,
  meme:{id,image,caption,sourceDate:string|null,isArchive:boolean,approvalStatus:'approved'}.
Use approved cast names, not raw offensive ESPN labels, in editorial display. Preserve source raw normalized names in source data only. Alias/character ID crosswalk comes from owner-approved Nov11 pairings/story and actual normalized team IDs; do not infer real identities from faces.

Daily story must explicitly say DAILY ROUND, never completed weekly win. Thresholds are transparent deterministic rules, not a claim of autonomous model intelligence. Daily margin <=5 acknowledges close; >=20 can roast a smoked daily result, ordinary otherwise. Only verified complete prior daily rounds count for rolling seven-calendar-day records. Three recorded daily-round losses can earn a 'bye week' joke, with exact daily count/window/coverage disclosed; never conflate with official ESPN matchup W-L. Do not claim an unbroken streak across missing dates/off-days. Start with honest thin history; grow as real archives accumulate. No invented player, goalie, active/bench or lineup claims. Weekly context is separate timestamped current snapshot only if same matchup period and participant pair, never retroactively called end-of-day.

## UI worker scope

Own src/pages/index.astro, src/pages/memes/index.astro, src/pages/recaps/index.astro, NEW src/pages/recaps/[date].astro, src/layouts/Layout.astro, src/styles/global.css, and tests/site.test.mjs plus NEW tests/daily-site.test.mjs as needed. Do not modify backend/config/workflows/other existing tests. New UI reads contract `recaps.json` and `editorial.json`; parent/backend will generate real seed. Keep sample route and clearly sample-specific labels, but stop globally calling verified daily aggregates DEMO. Prominent latest edition card on homepage, readable individual daily rounds with image + punchline, archive date navigation, focused meme-locker spotlight and functional combined tag/text/multi-manager filters. Show seven-AM target, Arizona date, actual fetched-at, separate weekly context timestamp, approval/fallback policy. Client freshness should reveal older-than-yesterday recap dynamically (no new network) when failed refresh leaves old site in place. Never imply reliable exact GitHub cron delivery or image generation configured. No browser ESPN calls/tracking/external assets.

## Workflow worker scope

Own NEW .github/workflows/daily-clubhouse.yml and scripts/test_daily_workflow.py ONLY. Existing manual deploy workflow stays untouched. Scheduled preparation **13:40 UTC =06:40 AZ**, not-before publication **14:00 UTC =07:00 AZ**, manual dispatch publishes immediately for verified setup/backfill. No inputs needed; default yesterday AZ. Document best-effort Actions jitter; no exact-time guarantee.

Separate jobs/security boundaries: collect (contents:read, ESPN secrets only fixed collect step, offline tests before credentials) -> publish (NO ESPN secrets, contents:write only here, download exact sanitized artifact, revalidate/import, stage ONLY `src/data/daily/*.json`, `src/data/current.json`, `src/data/recaps.json`, ordinary FF commit/push; output exact published SHA) -> build (NO ESPN secrets, checkout exact publish SHA, Node26 npmci--ignore-scripts, build/tests, upload dist ONLY) -> deploy (pages:write,id-token:write only here, github-pages environment, wait until14UTC on schedule only, never sleep beyond bounded timeout). Use workflow-level concurrency group pages, cancel false, repo/main gate every relevant job, sha-pinned actions, checkout persist-credentials false. No shell date interpolation inputs. `GH_TOKEN: github.token` only needed repository-push step, never credential-bearing remote URLs/printing token. Pull/rebase/force prohibited: fetch main and ordinary ancestry/race gate, fail rather than overwrite newer source. Failure at collect/import must not overwrite/publish good data; old deployed site ages visibly. No recursive workflow dispatch. Artifact exact normalized daily.json/current.json, retention1day. No partial upload/raw caches/reference folders.

Verified action pins:
checkout v6 d23441a48e516b6c34aea4fa41551a30e30af803
setup-node v6 249970729cb0ef3589644e2896645e5dc5ba9c38
upload-artifact v4 ea165f8d65b6e75b540449e92b4886f43607fa02
download-artifact v4 d3f86a106a0bac45b974a628896c90dbdf5c8093
upload-pages-artifact v4 7b1f4a764d45c48632c6b24a0339c27f5614fb0b
deploy-pages v4 d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e

## Worker discipline
Strict TDD RED/GREEN vertical slices, real offline tests; no network/install/credentials/branch switches/commits/push/deploy. No AGENTS edits or protected-file bypass. Report files, tests, honest limits. Parent integrates, exercises authenticated path, separate senior then security review final immutable manifest, local/browser QA and approved public deployment/readback.
