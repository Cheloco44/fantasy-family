# One-date ESPN daily-score lookup

This diagnostic answers the owner's request for aggregate fantasy points earned on **November 11, 2026, America/Phoenix**. It is separate from the public current-matchup dashboard and does not generate a recap, deploy a website, enable a schedule, or change an ESPN lineup.

## Evidence and limitations

- The public ESPN season schedule supplies game timestamps and scoring-period IDs. The collector verifies the Arizona date against that schedule; it must not infer the date by subtracting one from today's period. The requested date currently maps to scoring period **44**, not current period 45.
- The protected league read requests that exact scoring period. Only `schedule[].home/away.pointsByScoringPeriod['44']` is accepted as the aggregate daily score. `totalPointsLive` and `totalPoints` are not accepted as substitutes.
- Explicit period-44 score entries identify the matchup period; a unique candidate and complete eight-team coverage are required. Configured week groupings may differ from the actual entries and do not override date-keyed daily scores. The configured map is used only when no explicit daily entry identifies a period, and that fallback must itself be unique; daily totals still remain unavailable when missing.
- Team names and IDs are taken from ESPN, without guessing links to owner-supplied manager profiles.
- Zero is a valid daily score. A missing value is unavailable, not zero. Partial availability must be disclosed rather than called a complete result.
- Professional-game `statsOfficial` evidence is reported separately; even completed games may receive later stat corrections. These are the provider's scores as returned at collection time, not a preserved contemporaneous snapshot.
- This lookup does not verify historical active/bench assignments, player attribution, goalie rules, or an independently recomputed fantasy total. Those gates remain required before player/bench commentary or an accurate daily recap.

## Protected manual collection

After the new source has passed separate senior/security reviews and is registered on `main`:

```bash
gh workflow run lookup-daily.yml --repo Cheloco44/fantasy-family --ref main
gh run list --repo Cheloco44/fantasy-family --workflow lookup-daily.yml --branch main --event workflow_dispatch --limit 5 --json databaseId,headSha,status,conclusion,url
```

Select the run matching the reviewed source commit and inspect its job/step status. Do not print raw credentialed-job logs. The workflow enables opt-in `--diagnostic`: on failure it may emit one `SAFE_LOOKUP_DIAGNOSTIC` JSON line containing only a fixed stage, HTTP status, period ID, counts, fixed type labels, and identity/scoring-match booleans. No team names, scores, raw fields or exception text enter that diagnostic. A credential-collision check also covers this line. Extract only this prefix in-process; never display the full job log. Download only its `nov-11-daily-scores` artifact:

```bash
gh run download RUN_ID --repo Cheloco44/fantasy-family --name nov-11-daily-scores --dir artifacts/nov-11-RUN_ID
```

The only uploaded file is `artifacts/daily-lookup/nov-11.json`; artifact retention is one day. Check exact field allowlists, requested date/timezone, period, league/season, eight unique team IDs and each score's availability/source before reporting results. A green run proves retrieval/validation, not that all eight daily scores exist.

The CLI refuses network access without `--network`. GitHub Actions injects the existing owner-managed `ESPN_S2` and `ESPN_SWID` secrets into the collection step only. The public metadata request has no cookies. The authenticated request is a fixed HTTPS GET to the league endpoint, with redirects refused and response size/time bounded. Neither raw provider responses nor account/member/player records are saved. Output is normalized, checked for credential collisions, and atomically written; failure preserves a prior file. Never enter credentials in Discord.

Offline verification:

```bash
python -m unittest discover -s scripts -p 'test_*.py' -v
```

No credentials or network are needed for these synthetic tests. Passing them alone is not proof that the real date-specific data is available.
