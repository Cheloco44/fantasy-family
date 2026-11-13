# Daily clubhouse: 7 a.m. Arizona

## The publishing contract

- **Coverage:** the previous calendar day in `America/Phoenix`, not the previous UTC day and not the full weekly matchup.
- **Target:** 07:00 Arizona. Preparation is scheduled for 06:40 (13:40 UTC); scheduled deployment waits until at least 07:00 (14:00 UTC). GitHub Actions and Pages are best-effort services, so queue/build/deployment delays can make publication late. This is not an exact-time SLA.
- **Data:** fixed, authenticated, read-only ESPN GETs. No lineup, trade or transaction changes. The collector exports strictly normalized team aggregates and current standings/matchup totals only; no raw account/member/player records.
- **Humor:** daily rounds drive daily jokes. Close rounds are acknowledged; a 20-point-or-greater daily margin can get a smoked-result roast. These thresholds are editable in `src/data/editorial.json`, not mysterious model judgments. Fictional characters remain separate from real scores.
- **History:** approved, dated source bundles accumulate under `src/data/daily/`. Verified daily-round results support rolling seven-calendar-day records and recurring jokes. Three recorded daily-round losses can earn a bye-week joke, with the actual count/window/available coverage disclosed. These are NOT ESPN weekly matchup losses. Missing dates do not prove streaks. Thin history stays thin rather than being invented.

## Owner review: time to correct, not a last-minute approval race

All times are `America/Phoenix` (UTC−7 year-round):

- **04:30:** a separate read-only GitHub workflow prepares sanitized prior-day aggregates. It cannot publish source or deploy the website.
- **05:00:** Neo's own Hermes profile delivers an unpublished draft recap/image packet to the originating Discord conversation (this shared room, not a private DM). These are newly captioned composites of approved portraits, not new AI-generated poses. Draft files stay outside public source.
- **05:45:** a reminder asks for any remaining feedback.
- **06:00:** owner feedback/approval deadline. Reply here and mention Neo so the assistant actually receives the approval or edit request; it cannot search Discord history or infer an unseen reply.
- **06:00–06:30:** correction, reapproval if necessary, technical reviews, tests and ordinary reviewed source push. Work can begin as soon as feedback arrives; it need not wait until 06:00.
- **06:30:** correction/merge cutoff and final status notice. Only explicitly approved artwork actually present in the remote approved catalog counts as ready. A local draft, chat approval alone or pending commit is not proof it reached the publishing source.
- **06:40:** existing daily publication preparation/checkout target. Its exact checked-out revision is the binding snapshot; queue delays do not extend the editorial deadline.
- **07:00:** existing not-before scheduled deployment target. GitHub scheduling/Pages and Discord delivery remain best effort, not exact-time guarantees.

No response, a failed review preparation/delivery, a missed cutoff, or an uncompleted correction means **use already approved suitable art/portraits**, not a draft and not a delayed edition waiting indefinitely for approval. A late setup/test packet is labeled late and is not evidence that its 05:00 review delivery occurred. The first regular early-review cycle begins after setup, not retroactively this morning.

The three Hermes jobs are script-only (`no_agent`), so preparing and sending the review packet/reminders do not depend on an inference-model quota. The gateway/VPS, GitHub access and configured Discord adapter must still be running. The website's independent GitHub workflow retains its safe fallback if the local review service is unavailable. See [REVIEW-OPERATIONS.md](REVIEW-OPERATIONS.md) for setup, exact scripts, canary verification and recovery.

## Images: approval first; absence is not approval

Newly created or newly supplied family memes remain in ignored `private/meme-drafts/` or `artifacts/` while the owner reviews them. Do not commit unreviewed images to the public repository, even outside `public/`. A chat attachment provided for style learning is not blanket publication consent.

After explicit owner approval:
1. Strip image metadata and export only the intended derivative to `public/memes/approved/`.
2. Add a unique entry to `src/data/editorial.json.approvedMemes`, with relative image path, caption, original context date, character-manager slugs, tags, `approvalStatus: "approved"`, and `contextType` (`dated` or `evergreen`). If the image contains baked-in daily scores, record `scoreContext` as exact ESPN-team-ID-string → daily-points pairs. A later correction that disagrees with those values forces approved fallback art. Review/commit/publish that exact change.
3. Finish correction, explicit owner reapproval of changed images, technical reviews/tests and the reviewed ordinary source push by **06:30**. The daily run uses the approved catalog from its actual checked-out revision. Chat approval not committed/pushed into that source is not publication readiness; late approval is not assumed to be included in that edition.

If there is no approved new image, the daily edition uses approved existing artwork or an approved character portrait. It does NOT wait for a reply and does NOT publish a draft. A dated scoreboard meme is used for its own date only; the locker can retain it as a clearly dated archive item. Old baked-in numbers are never passed off as today's score.

No image-generation provider or paid service is configured. Scheduled editions can always use approved art. New cinematic fight poses/scenes must be produced and reviewed separately; captioned composites are described as composites, not falsely called new AI-generated scenes. The first approved batch consists of four November 11 composites. Full reference folders/contact sheets/private manifests are not website content.

## Editorial learning

The owner-approved cast and current lore define each recurring character. New family memes and feedback refine a local style guide: cinematic cartoon rivalry, underdog ambushes, oversized reactions, absurd loser-comfort scenes and short punchlines. Update that guide and approved templates after feedback. Do not imply that a model permanently retrains itself from chat images.

Daily text is generated by deterministic, reviewable templates from real aggregate scores and archived daily results. The system does not invent player/goalie highlights, historical active/bench comparisons, real quotations or private biographical facts. Those require separate verified data/approval. The global and profile fiction disclosures remain visible.

## Running the flow

After reviewed source reaches `main`, **Actions → Daily clubhouse → Run workflow** performs an immediate end-to-end refresh and publication. Scheduled runs prepare at 06:40 and gate publication until 07:00. Manual runs are immediate for setup/recovery and do not promise to wait for the morning window.

Offline source commands:

```bash
python scripts/daily_pipeline.py rebuild
BASE_PATH=/fantasy-family/ ASTRO_TELEMETRY_DISABLED=1 npm run build
npm test
python -m unittest discover -s scripts -p 'test_*.py' -v
```

The collection CLI requires explicit `--network`; cookies come only from the existing owner-managed Actions secrets `ESPN_S2` and `ESPN_SWID`. Never paste them in chat or put them in files. The public schedule request never receives cookies. Raw credentialed logs are not chat diagnostics.

## Security boundaries and failure behavior

- Collect job: repository read permission; ESPN cookies only in the fixed collection step after offline tests.
- Publish job: no ESPN cookies; revalidates the exact sanitized artifact, imports date-keyed bundles and ordinary fast-forward commits ONLY the allowlisted source JSON paths. Races fail instead of overwriting another source change.
- Build job: no ESPN cookies; checks out the exact published revision, builds/tests and uploads only `dist/`.
- Deploy job: Pages/OIDC permission only; does not receive ESPN cookies.

Validation/collection/import failures preserve last-good data and do not deploy partial results. The existing site's dates and client freshness warnings reveal an older edition/snapshot; a failed run does not falsely stamp old data as fresh. An unavailable daily value is not zero. Off-days and provisional/incomplete results are labeled and do not create fake daily wins/losses. Later provider corrections update the same date key and rebuild affected trend calculations rather than duplicating editions.

The website workflow changes the website, not Discord. A separate Hermes `neo` script-only review service sends the 05:00 packet and two status messages to the originating Discord conversation; it does not broadcast to family channels or search chat history. The published link remains shareable. Verify the exact Actions run/revision and public page before claiming a website refresh succeeded; verify cron delivery status separately before claiming review messages were sent.
