# Current ESPN standings and matchup snapshot

## Scope and verification status

This collector is **implemented and tested offline, not verified against an authenticated real ESPN response**. An authenticated real run and comparison of the exported standings/scores against ESPN are still required before claiming retrieval or scoring correctness. An earlier settings probe does not establish either of those gates.

The owner approved public ESPN team names, standings and matchup scores. This phase exports **current standings and current cumulative matchup scores only**, for league `1399646897`, ESPN season `2027`, exactly eight teams. It does not export NHL player statistics, rosters, daily contributions, historical lineups, history, recaps or category recomputations. It never maps ESPN team IDs/names to clubhouse manager profiles automatically. Team names come from ESPN, not aliases or profile guesses.

This is a **manual snapshot, not realtime data**. `mode: "live"` identifies ESPN-sourced rather than sample data; it does not mean continuously updated or verified accurate. Show `fetchedAt` and snapshot/staleness wording. Do not describe an entire matchup score as today's performance or as a final result.

## Execution and safety boundary

Python standard library only. The safe default refuses network access and writes nothing:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/collect_current.py
```

The latter exits `2`. Tests use synthetic data, sentinel cookies and injected openers; they never read real credentials or contact ESPN. Test temporary files follow the host's configured temporary directory. `normalize(data, now=..., expected_team_count=2)` supports small offline fixtures; the production CLI always requires eight teams and has no team-count override.

The separately authorized manual Actions collector runs this command with both cookies supplied **only through that step's environment**:

```sh
python3 scripts/collect_current.py --network
```

Default output is `artifacts/current-export/current.json`; `--output PATH` selects a local output path. No cookie argument, `.env` loader, custom URL, retries, redirects, certificate bypass, request-body payload or debug/trace output is supported. Do not run the network command merely to test the implementation.

The sole request is a fixed GET to:

```text
https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/2027/segments/0/leagues/1399646897?view=mSettings&view=mTeam&view=mMatchupScore&view=mScoreboard&view=mStandings
```

TLS uses Python's default certificate and hostname verification. All redirects, including same-host redirects, are refused. Socket timeout is 20 seconds; the response is read with an 8 MiB + 1 byte bound and anything over 8 MiB is rejected. There is one request attempt and no retries. Both nonempty `ESPN_S2` and `ESPN_SWID` are mandatory before constructing the opener. Cookie validation matches the existing probe: reject characters outside ASCII 33–126 and semicolon, comma, double quote or backslash, without echoing the value.

**These are account session cookies, not league-scoped read-only credentials.** They may grant broader account access even though this client only makes a read-only GET. Never retrieve their actual values into chat, files, source, screenshots or logs. Keep credentials in the owner-managed GitHub Actions secrets `ESPN_S2` and `ESPN_SWID`. Do not enable shell tracing, HTTP debugging, environment dumps, core dumps, response logging or traceback diagnostics in the credentialed process. In-memory cookies and responses are not guaranteed to be zeroized; a compromised runner or authorized process inspector remains a risk. Rotate/revoke exposed or obsolete sessions and follow ESPN's terms.

## Normalized contract (schemaVersion 1)

Only the following allowlisted keys are constructed. No raw provider object is forwarded:

- Root: `schemaVersion: 1`, `mode: "live"`, `source: "ESPN"`, `dataKind: "current-matchup-snapshot"`, `fetchedAt` (UTC ISO timestamp ending in `Z`), `leagueId: 1399646897`, `seasonId: 2027`, `scoringType` (`H2H_POINTS` or `H2H_CATEGORY`), positive integer `matchupPeriodId` and `scoringPeriodId`, `teams`, `matchups`.
- Team: `id`, `name`, `standing` (positive integer or null), `wins`, `losses`, `ties`.
- Matchup: `id`, `home` (SIDE), `away` (SIDE or explicit null for a bye).
- SIDE: `teamId`, `points` (finite number or null), `pointSource` (`totalPointsLive`, `totalPoints`, or null), `categoryRecord` (`{wins, losses, ties}` or null), `available` (boolean).

Source interpretation:

- `settings.scoringSettings.scoringType` must be exactly one of the two supported formats. Unknown/missing formats fail closed; no assumption of points scoring.
- `status.currentMatchupPeriod` selects schedule entries by exact integer `matchupPeriodId`. Root `scoringPeriodId` is separately retained and **is not the current matchup period**. Historical schedule entries are not exported.
- Team identity is `teams[].id`, with ESPN `name` or, when that key is absent, legacy `location + " " + nickname`. Names must be nonblank strings of 1–120 characters without control/format/surrogate characters. Optional `playoffSeed` becomes `standing` only if it is a positive nonboolean integer; otherwise standing is null. `record.overall.wins/losses/ties` are all required nonnegative integers.
- All eight teams must be distinct and each must participate exactly once in the current schedule, including byes. Current matchup IDs must be unique; home/away IDs must join to the teams and cannot be repeated. An absent away key or explicit `away: null` denotes a bye; all teams still must be accounted for exactly once, so incomplete schedules fail. Partial/empty schedules fail rather than promoting partial data.
- `H2H_POINTS`: use finite numeric `totalPointsLive` when the key is supplied; an invalid supplied value fails rather than silently falling back. Otherwise use finite numeric `totalPoints`, with `pointSource: "totalPoints"`. **That fallback is not guaranteed to be a live total** and the source must remain visible to consumers. If neither key exists, use `points: null`, `pointSource: null`, `available: false`, not a fabricated zero. A genuine numeric zero is available. `categoryRecord` is always null.
- `H2H_CATEGORY`: read only side `cumulativeScore.wins/losses/ties`, all nonnegative integers. `totalPoints` and `totalPointsLive` are not category scores and are ignored. Missing/null cumulative record is unavailable. When all three counts are zero and nested `cumulativeScore.scoreByStat` is absent, null or empty, export `categoryRecord: null`, `available: false` rather than claiming verified 0–0–0. A nonempty object-shaped `cumulativeScore.scoreByStat` is only availability evidence; its contents are neither recomputed nor exported. Nonzero valid cumulative counts are available. Both points fields remain null.
- Booleans are not integers or points. Nonfinite points, missing records/periods, invalid league/season, duplicate teams/participants/current matchups and malformed required fields fail normalization. Consumers must retain the distinction between unavailable and zero.

Members, owners, account names, logos, email addresses and every other unapproved source field are discarded. The only approved names emitted are the ESPN team names. Before writing, serialized normalized output is checked for either supplied cookie value; any collision fails. This defense also catches accidental cookie values in approved name fields.

## Persistence and safe results

Raw responses are never persisted or printed. The complete response is normalized, serialized without NaN/Infinity and checked for cookie collisions **before any output write**. Only that normalized JSON enters a same-directory temporary file, which is flushed/fsynced and atomically replaced into the output path. Failed fetching, validation, secret checks or replacement preserve an existing last-good output; temporary normalized files are cleaned up on ordinary failures. An abrupt process/host kill can leave a normalized temporary file; no raw-response file is created. The workflow uploads the exact final filename, never a directory or wildcard.

Exit status / emitted output:

- `0`: `OK teams=8 matchups=<count> scoringType=<supported format>` only. No names, raw JSON or output paths are logged.
- `1`: `ERROR collection failed.` Covers missing/invalid cookies, redirects/auth/HTTP/network errors, malformed/oversized responses, normalization/secret checks and output failures, without exception details.
- `2`: `ERROR network disabled; pass --network.` or sanitized `ERROR invalid arguments.` for CLI errors. CLI help is static and contains no league response or credential values.

No response body, request header or traceback should be added to troubleshoot these errors. Check owner-managed secret presence and the reviewed source/schema privately rather than printing provider responses.

## Manual Actions artifact — no deployment

`.github/workflows/refresh-current.yml` accepts `workflow_dispatch` only and restricts the job to `Cheloco44/fantasy-family` on `refs/heads/main`. It grants `contents: read`, pins checkout to `11bd71901bbe5b1630ceea73d27597364c9af683` and sets `persist-credentials: false`.

Offline probe, workflow and collector tests run first without ESPN cookies. Only the final collection run step receives the two secrets; shell tracing and core dumps are disabled. A **separate upload action step with no credential environment** uses `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02` to upload exactly `artifacts/current-export/current.json` as `current-league-data`, with one-day retention and `if-no-files-found: error`. Upload runs only on preceding success. Treat artifacts/logs in a public repository as potentially visible; the artifact contains only approved public fields.

After reviewed changes reach main, an authorized owner can manually select **Actions → Refresh current ESPN snapshot → Run workflow → main**. This implementation work did not dispatch it. Read back the actual run/head SHA and artifact before claiming it succeeded. This workflow does not commit source/data, publish Pages, modify ESPN, run on a schedule or update the website automatically. Downloading/importing a reviewed snapshot into a frontend is a separate step; the site build never receives cookies.

## Actual offline TDD evidence

Executed locally using `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p test_collect_current.py -v`, with feature slices added before their implementations:

| Slice | Actual RED result | Actual GREEN result |
| --- | --- | --- |
| Points allowlist and matchup-vs-daily period | `Ran 1 test`; `FAILED (failures=1)` — missing collector assertion | `Ran 1 test`; `OK` |
| Categories, unavailable scores, explicit byes | `Ran 3 tests`; `FAILED (failures=1, errors=1)` — points incorrectly used / missing-score key unsupported | `Ran 3 tests`; `OK` |
| Strict validation, legacy names, optional standing | `Ran 6 tests`; `FAILED (failures=45, errors=7)` — malformed subcases not rejected / required validation missing | `Ran 6 tests`; `OK` |
| Opt-in authenticated fixed GET, caps/privacy/atomic preservation | `Ran 10 tests`; `FAILED (failures=1, errors=13)` — CLI missing | `Ran 10 tests`; `OK` |
| CLI entrypoint and manual workflow | `Ran 13 tests`; `FAILED (failures=2)` — entrypoint and workflow missing | Full suite `Ran 20 tests`; `OK` |
| Malformed category score evidence | `Ran 15 tests`; `FAILED (failures=1)` — nonobject evidence accepted | Full suite `Ran 22 tests in 0.246s`; `OK` |

The final full-suite command was:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

It passed 15 new collector/workflow tests plus the seven existing offline probe/workflow tests. Coverage includes synthetic private-field/cookie sentinels; period separation; points vs categories; numeric zero vs missing; unknown format; names/records/duplicates/partial data; byes; redirects/auth/network failures; response cap; mandatory cookies; no-opt-in/no-output; default output path; replace-failure last-good preservation and temp cleanup; real opener configuration without making a connection; CLI sanitization; and workflow secret/artifact boundaries. No ESPN traffic, actual secret reads, commits, pushes or deployment occurred. Fixture tests cannot establish ESPN schema availability or real scoring correctness; those gates remain open.
