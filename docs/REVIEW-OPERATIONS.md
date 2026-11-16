# Early review service operations

## Separation of responsibilities

- `.github/workflows/prepare-review.yml`: live collection to the normalized two-file artifact `daily-review-input`, one-day retention, read-only, no repo/Pages writes. Its GitHub `schedule` cron was historically unreliable (zero schedule runs observed; even `daily-clubhouse` fired hours late), so a reliable local trigger fires it instead: Hermes `neo` job `Clubhouse 04:30 Arizona review prep trigger` runs `possum_review/prepare_dispatch.py` at **04:30 Arizona / 11:30 UTC** via `gh workflow_dispatch` (`ad2ade2020e9`). Keep both; the Hermes dispatch is the dependable path.
- Hermes profile **neo**: 05:00 packet, 05:45 reminder, 06:30 cutoff notice, delivered to the **originating Discord room**. This is a shared room, not a DM or a confidentiality boundary. No automatic family-channel blast.
- `.github/workflows/daily-clubhouse.yml`: unchanged 06:40 preparation target and 07:00 not-before scheduled deployment gate. No new dependency on a successful review packet or owner reply.

All schedules are best effort. The existing safe approved-art/portrait fallback is the availability path, not unreviewed publication. Local Hermes review delivery needs the VPS/gateway, configured Discord adapter, GitHub CLI authentication and Pillow. Collection uses only owner-managed Actions secrets; the local script never obtains ESPN cookies or makes credentialed ESPN requests. Script-only scheduled execution avoids inference quota/rate-limit dependency; subsequent owner-requested creative revisions still need an available assistant/operator.

## Reviewed runtime snapshot, not a mutable feature checkout

The packet driver and its four existing pure/helper imports are copied after final reviews into the **current profile only**:

`~/.hermes/profiles/neo/scripts/possum_review/`

- `review_packet.py`
- `daily_pipeline.py`
- `collect_current.py`
- `lookup_daily.py`
- `probe_espn.py`

The packet driver plus the thin `review_packet_reminder.py` and `review_packet_cutoff.py` entry scripts invoke `packet`, `reminder` and `cutoff`. They run this reviewed snapshot, not code from whatever uncommitted/feature branch happens to be checked out tomorrow. Source config, portraits and bounded archive data come from exact Git objects of the successful preparation run/current remote main, not unreviewed working-tree edits. `git fetch` changes remote-tracking refs only; there is no automatic pull/reset/branch switch or working-tree modification.

Use the supported cron API/CLI; never hand-edit another profile's jobs. Register jobs paused, verify a real packet, run one delivery canary, inspect its durable delivery status, then enable recurring schedules. On this UTC scheduler the five-field expressions are:

- Packet: `0 12 * * *` → 05:00 Arizona.
- Prep dispatch: `30 11 * * *` → 04:30 Arizona (fires `prepare-review.yml` via `gh`).
- Reminder: `45 12 * * *` → 05:45 Arizona.
- Cutoff: `30 13 * * *` → 06:30 Arizona.

Verify the stored **next_run_at** values in Arizona after creation rather than trusting host timezone assumptions. The 04:30 prep dispatch and the 05:00 packet are separate jobs; if the prep runner is slow, the 05:00 packet reports "unavailable" safely and can be re-run after the prep completes. Keep origin routing set by the current conversation's runtime; do not guess a Discord channel ID from a display label. Set `no_agent: true`, a fixed profile-relative script, and the scoped project `workdir`. No provider/model pin is needed.

Runtime installation and delivery receipts are local operational evidence, not website assets. Do not publish raw gateway logs, credentials, cron routing identifiers or private manifests.

## Owner approvals and corrections

The 05:00 packet includes coverage date, actual source-run evidence, captioned draft composites and candidate identifiers/hashes. Drafts are new layouts of approved portraits, not new AI-generated poses/scenes. The script does not read Discord history and cannot infer consent. The owner should reply **in this room and mention Neo**, identifying which images are approved or what should change.

A live assistant handling the reply must:

1. Load `neo-engineering` and this guide. Inspect the exact current packet/manifest for yesterday's Arizona date. Verify each selected file's current hash equals the reviewed manifest. Validate source evidence and exact score context; do not promote a stale/previous date or different bytes just because an older packet was approved.
2. Resolve which candidate(s) the owner explicitly approved. Requested edits alone are not approval of unseen changed images. Make corrections privately, return the corrected derivative for owner review, and retain original source/stat evidence.
3. **After explicit approval of final bytes**, export only intended metadata-free derivatives into `public/memes/approved/`. Add unique dated `approvedMemes` entries with exact image path, caption, `managers`, tags, `approvalStatus: "approved"`, `contextType: "dated"`, `date` and the manifest's exact team-ID → daily-score `scoreContext`. Use the actual schema validated by `daily_pipeline`; do not guess property names from this checklist.
4. Rebuild/test offline with existing source plus the verified date bundle. Run separate senior review and then security review bound to final changed bytes; correct findings and re-review as needed. Stage only scoped approved files, ordinary commit/push; verify remote source. Never force-push, change repository settings, alter the 07:00 gate or publish another pending draft.
5. Finish approval/corrections/reviews/push by **06:30 Arizona**, leaving a 10-minute buffer before the 06:40 checkout target and the existing build/deploy window. If any gate cannot finish, leave approved fallback in place. Later owner instructions can authorize a separately reviewed recovery/update; do not silently present it as on-time morning publication.

The 05:45 and 06:30 notices check what is really approved **and present with matching bytes in remote main's catalog**. They do not treat chat approval, a local pending file or silence as completion. No scheduled script promotes drafts. The normal daily selector still rejects dated art on the wrong day and score-bearing art after relevant stat corrections.

## Verify and recover

```bash
# Profile-scoped; never read/modify another profile's cron data.
hermes --profile neo cron list
hermes --profile neo cron status
hermes --profile neo cron doctor
hermes --profile neo cron runs

# Source/read-only prep metadata, not credentialed raw logs.
gh run list --repo Cheloco44/fantasy-family --workflow prepare-review.yml --limit 5 \
  --json databaseId,headSha,status,conclusion,createdAt,url

# Manual read-only preparation; does NOT deploy the website.
gh workflow run prepare-review.yml --repo Cheloco44/fantasy-family --ref main

# Test code locally without sending a Discord message.
python scripts/review_packet.py packet
python scripts/review_packet.py reminder
python scripts/review_packet.py cutoff
python -m unittest discover -s scripts -p 'test_*.py' -v
```

`MEDIA:` lines from a local test are output paths, not proof of Discord delivery. A cron run's success does not prove image attachments were delivered: inspect its specific durable delivery result and partial-delivery errors. The canary must actually exercise the configured origin route. No read receipt is implied; user confirmation remains the only proof the owner saw a packet.

On missing/late/invalid prep artifacts, the script reports a sanitized review-unavailable notice and does not relabel older data as yesterday. Inspect allowlisted run metadata, repair/rerun the separate read-only prep, and retry the packet job if time permits. Do not paste credentialed logs or substitute sample data. A packet run after 06:00 is labeled late/setup; it cannot retroactively satisfy that morning's review window. Off-days/incomplete totals are labeled without fake winners or invented historical streaks.

To roll back review delivery, pause only these three `neo` jobs. The independent website schedule and approved fallback continue unchanged. To update the installed snapshot, review/test new exact files first, pause the jobs, replace only this profile's scoped scripts, verify hashes and a canary, then resume. No global gateway restart or changes to another profile are required.
