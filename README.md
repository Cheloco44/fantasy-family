# Redlands Possum Busters

An Astro clubhouse demo for the 2026–27 Redlands Possum Busters ESPN Fantasy NHL league. Marcelo approved publishing this demo source and a manual read-only access-check workflow to `Cheloco44/fantasy-family`. **No website deployment, daily schedule, or actual league-data publication is approved or enabled.**

## Actual status

- Local content-review update: eight owner-supplied manager/team pairs and character references now replace the two demo identities. These changes are not pushed or approved for public release yet. Bios, images, favorite NHL teams, scouting reports and ESPN team-ID mappings remain pending.
- Working: static dashboard, profile routes, sample recap/archive, three original demo meme images (unassigned to real managers), combined tag/manager/text filters, mobile navigation, explicit not-connected status.
- Verified: the unauthenticated league settings request returned HTTP 401. This is an access blocker, not an empty league.
- Not working yet: actual league retrieval; scoring subtype/settings; historical rosters; real daily recaps; automated updates; stat correction handling; persistent last-good datasets. The access probe is not a completed adapter.
- No manager details, real NHL results, league standings, biographies, championships or quotes are fabricated. No accounts, uploads, paid AI, external frontend scripts or tracking.

## Local setup

Use a Node version satisfying `package.json`'s pinned Astro dependency. The initial build was exercised with Node 26.12.1 and npm 12.0.2. Python scripts use only the standard library.

```sh
npm ci --ignore-scripts
ASTRO_TELEMETRY_DISABLED=1 npm run build
npm test
python -m unittest discover -s scripts -p 'test_*.py' -v
npm run dev
```

The development URL is printed by Astro and binds to 127.0.0.1 only. For an already-built preview:

```sh
python -m http.server 4173 --bind 127.0.0.1 --directory dist
```

On your PC, tunnel to the VPS without opening a public port:

```sh
ssh -L 4173:127.0.0.1:4173 marcelo@YOUR_VPS_HOST
```

Then open http://localhost:4173 on that PC. Replace YOUR_VPS_HOST locally; do not send server credentials in Discord. This is a local preview URL, not a publicly accessible link.

## Edit approved content

`src/data/clubhouse.json` is the single starter content file. Manager labels and character references in the local preview are owner-supplied; all actual results, recaps and artwork remain demo or unavailable. Do not remove the demo-data banner or publish new profile records before explicit content approval. The vault folder named "nhl fantasy images" was not present in the VPS copy when checked; wait for sync or an exact path rather than inventing image matches.

- Profiles: edit aliases, team name, initials and biography. Only use self-written, explicitly approved bios. Current UI has no real avatar/logo upload or championships editor; those are future content extensions.
- Memes: put approved static images or GIFs in `public/memes/`; add a metadata record with a unique id, relative image path, caption, contributor nickname, ISO date, manager slug, tags and featured flag. Keep exactly one featured meme. No SVG supplied by untrusted contributors: sanitize/convert it first. Strip image location/EXIF metadata. Use only content you have permission to share.
- Search matches captions; tags and manager filters combine. Reset restores all content. The gallery still displays without JavaScript.
- No HTML in text fields; Astro escapes text. Local source editors are trusted administrators, not anonymous uploads. Validate image paths and do not embed external tracking resources.

Optional manager avatar/logo, favorite team, approved scouting report, championships, rivalries and league moments should be added only from approved submissions. Nothing about real managers is assumed. Existing placeholder fields intentionally say not supplied.

## ESPN access

Read `docs/ESPN-SETUP.md` for the private terminal probe and manually dispatched GitHub Actions access check. Never paste cookies in chat. No `PUBLIC_` credential variables, cookies in config, `.env` files in commits, raw ESPN records in `public/`, or secrets in Actions logs/artifacts. Session cookies may be account-wide even though our client only sends GET requests.

## Integration contract — not implemented yet

1. Retrieve settings and prove whether head-to-head uses points or categories. Establish scoring periods and matchup periods; do not conflate them.
2. Exercise actual historical active/bench assignments and per-game player statistics for the same league-local day. If history is missing, report unavailable and start snapshots only after authorization; never substitute today's roster.
3. Score via real settings; compare with ESPN. Goalies require appropriate weighted totals and minimum-appearance rules. Category formats cannot be turned into invented fantasy point totals or ranked without an agreed criterion.
4. Map games to Arizona calendar dates. Distinguish off-days, postponed and incomplete games. Keep recap provisional if any expected results/lineups are missing.
5. Store private input only where necessary, outside the public site and artifact paths. Publish an explicit allowlist of approved fields, not a raw API payload. Use stable internal manager IDs mapped to separately approved aliases, not ESPN member names.
6. Before replacing last-good data, validate every required field, scoring rules and completeness. On failure preserve it and record a sanitized failed-attempt status. A stale badge must never imply a failed refresh succeeded.
7. Key recap records by league + season + Arizona date; corrections replace the same record with revision metadata. Re-fetch a recent correction window. Build content atomically; keep dated archives.
8. Test live scoring, lineup attribution, category ratios, goalie constraints, boundaries, off-days, missing results, corrections, repeated dates, failure preservation and credential exclusion before declaring live integration done.

The small tested `src/lib/clock.mjs` utility implements the Arizona calendar boundary. It is not a scoring engine or scheduled updater.

## Scheduling proposal — disabled

05:00 America/Phoenix corresponds to 12:00 UTC year-round. A future GitHub Actions schedule would use `0 12 * * *` with manual dispatch. GitHub scheduling can be delayed. No daily refresh is installed or scheduled. A manual-only ESPN access-check workflow is included. Use GitHub repository Actions secrets (not variables); never run credentialed jobs for untrusted PR code. Pin actions to verified commit SHAs and keep permissions minimal. Hosting/Actions allowances must be checked before enabling; no paid services without approval.

## Publication instructions — gated

Once Marcelo provides the GitHub repository and approves the exact public content:

1. Configure `site` in `astro.config.mjs` for the approved URL and set `BASE_PATH=/REPO_NAME/` when building a project Pages site (use `/` for a root/custom-domain site).
2. Run the build and tests under the actual base path; validate internal links, scripts and image URLs.
3. Senior review, security review and preview QA of the exact revision. Scan source and generated artifacts for credentials, PII, raw league responses and accidental personal files.
4. Use an approved Pages deployment workflow that uploads **only `dist/`**. Do not upload the whole working directory. No workflow has been installed yet.
5. Get final deployment approval. Verify the actual remote Pages URL and published content before saying it is live.

GitHub Pages is public for this design. A private repo is not a privacy control for the resulting site. `noindex` discourages indexing during review; it is not authentication. GitHub maintains visitor IP logs. Aliases, photos and league activity can still identify people, so all specific content needs explicit approval.

## Troubleshooting

- Build failure: `npm ci --ignore-scripts`, then rerun build; check supported Node version and JSON syntax.
- Blank styling or broken assets on Pages: check `BASE_PATH`, trailing slashes and the deployed subpath.
- Probe HTTP 401/403: stop; authenticate privately and rerun the probe. Do not paste response bodies or credentials into an issue.
- Probe succeeds: proves settings access only, not scoring/roster history or recap correctness.
- Stale status today: expected; the preview is not connected. There is no working refresh button pretending to call ESPN.

## Cost and scope

No new paid service, account or repository created. Only demo source and the manual access-check workflow are approved for publication. No transaction, trade or lineup mutation. No modifications to the gym app. A usable sample preview is not the first live-data milestone.
