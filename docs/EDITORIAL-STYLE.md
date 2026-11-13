# Clubhouse editorial style: receipts first, gloves off

## Owner-approved voice

The owner explicitly asked: “please learn and adapt to our style. im okay with savage headlines and banter. these guys deserve to get roasted. also update the site”. This is permission for reviewed sharper **text**, not blanket approval of images or publication of private material.

Write for the NHL clubhouse group chat, not a corporate sports newsletter. Savage family/league roasts, cartoon humiliation, mild profanity, cooked metaphors and non-graphic body-bag jokes are welcome. Make the punchline specific to the approved character and the actual daily result. The Commissioner gets return fire like everybody else; ordinary verified daily losses are fair game, not just blowouts. Winning managers can be ridiculous too.

The cast is fictional league characterization layered over real aggregate scores. The site already carries global/profile fiction disclosures; do not bolt an audit paragraph or repeated disclaimer onto every joke. Never present narrator gags, cartoon sounds or machine readouts as real attributed quotations.

## The scoreboard earns the headline

- Use the existing approved cast/ID mapping and display labels. Keep provider names and normalized source bundles untouched. Preserve `CAVE N1KGAR` (including its space) and `IR BOB` exactly; do not normalize, expand or improvise these labels.
- Only `verified-aggregate` editions award a daily result or result-based roast. The headline leads with the **largest actual opponent-to-opponent daily margin**, names both winner and roasted loser, and includes that margin. Do not substitute the highest individual daily total or a weekly/live total.
- A margin **at least the catalog's `smokedMargin`** earns the cooked/body-bag treatment. Defaults remain 20 smoked / 5 close; read the catalog, not hardcoded editorial assumptions. Equal leading margins use the lowest matchup ID, independent of provider ordering. Generation is deterministic and reviewable, not an autonomous intelligence claim.
- Close means margin **at most `closeMargin`**: admit the squeaker. A narrow edge is not a demolition, landslide or humiliation by invented numbers. The loser can get a character jab without pretending the round was a rout.
- Standard rounds get a sharp daily receipt, not a fabricated blowout. Ties have no daily winner or loser; do not crown a high-scoring tied team. Incomplete/provisional evidence stays on hold, even if a visible provisional number looks enormous. Missing is not zero. Off-days stay neutral and create no daily points or W/L.
- Keep the daily-versus-still-open-weekly distinction **once at page level**, using the existing component qualifier. `DAILY ROUND` / `daily rounds` remain allowed as UI labels/topics, not headline, card-title, story or dek prose (including hyphenated forms). Remove filler prefixes and constructions like “in the DAILY ROUND body bag”; do not merely change their case. Do not repeat a not-weekly disclaimer on every card. Weekly context remains separately timestamped and pair/period matched in closed Data details. No claims of a finished weekly win, weekly loss or end-of-day weekly total. Missing/provisional/off-day warnings remain visible and explicit.
- Preserve meaningful archived-history chirps: at least three verified daily losses/wins in the seven-calendar-day window before the supported recurring joke appears. Use the exact daily count. Limit visible history to at most two brief notes per edition, in stable matchup-ID order, rather than appending the same record commentary to every card. Keep all underlying counts/window/coverage/evidence in existing trend/data details. Missing dates/off-days cannot establish consecutive streaks; never relabel daily losses as weekly losses.

## Recurring characters, not interchangeable insults

| Cast | Use | Do not invent |
| --- | --- | --- |
| The Commissioner | Throne, tiny sports dictatorship, constitution, suspiciously convenient rules; losing exposes that being in charge awards no points. | Real misconduct or actual rule changes not established by evidence. |
| The Juice | Absurd **cartoon** supplement/roid horsepower, imaginary blender, bargain-bin comeback movie, all that power still needing a jump-start. | Real drug use, tests, crimes, health facts or fresh allegations. |
| June Bug | Polite assassin, thank-you card with a daily receipt, bug-zapper reversal; the courtesy makes the ambush worse. | Actual messages/quotes or unverified roster/player highlights. |
| Ben Bunny | Complaint department, arithmetic under protest, threat to quit, still not pressing unsubscribe; even winning is inconvenient. | MMA characterization or new real biography. |
| The Caveman | **Neanderthal / Stone Age** slapstick and blunt cartoon sounds: **UGG, GRONK, BONK**. Both wins and losses should sound prehistoric: drag home a receipt; try fixing Wi-Fi with a rock. | A real quotation, personal/intellectual diagnosis, or targeting a real ethnicity. These are the owner-approved cartoon persona. |
| IR BOB | Team Anti-Commish and the **imaginary**, unnamed team-mom group chat; absurd recruiting meetings and fictional carpool bureaucracy. | Real spouses, identifiable outsiders, private personal references or new biography. |
| Auto Erik | **Robotic, Skynet-ish machine syntax** in both outcomes: `SYSTEM:`, `STATUS: DAILY VICTORY`, `STATUS: DAILY ERROR`, reboot, denied requests, factory reset, demotion to toaster. | Real computer access, actual system events or fabricated lineup decisions. Readouts are fictional narrator bits, not real logs/quotes. |
| Jive Turkey / Young Monkey | AI as the designated scapegoat; dishes out banter and gets return fire with postage due. | New real personal facts or blaming actual provider errors without evidence. |

The latest owner direction specifically asks for Neanderthal references/sounds for the Caveman and robotic/Skynet delivery for Auto Erik. Carry that voice through **both** victory and loss branches, not just a profile heading. Approved lore remains the character source; do not revive superseded bits.

## Variety is part of the contract

The owner's correction was: “These update are the same. Redundang daily rounds. It’s okay in topic. But in the sentence it’s not needed”. A different name, date, number or synonym in the same oven/body-bag/receipt sentence is not a new joke.

- Use separate curated winner-character headline premises, loser-character card premises, and complete win/loss story beats for every approved character. The factual lead names both opponents and the actual margin; `escapes` / `outpoints` / `cooks` or `smokes` express the unchanged score classifications. The following character premise must do the comedic work. No assembly line of “hands X the receipt” or “puts X in the body bag” titles.
- Story beats vary in **both outcomes**; the Commissioner is not exempt. Keep Neanderthal language and UGG/GRONK/BONK for the Caveman and fictional SYSTEM/STATUS/Skynet delivery for Auto Erik across variants. Preserve the cartoon/imaginary qualifiers on the Juice and IR BOB premises; Ben stays in the complaint department, not MMA; Kyle gets return fire; June Bug stays the polite assassin.
- Selection is offline and bounded: a stable SHA-256 seed of date, matchup ID, character and copy channel chooses a starting point in a finite curated pool. Scan that pool to avoid gags already selected in the edition or the immediately previous archived edition. Process dates chronologically and matchups by ID, then display newest first; input ordering must not change generated copy. The headline has a separate pool from its own card.
- The guard tracks complete curated joke text, not rendered aliases or score tokens. If a pool is exhausted, prefer within-edition uniqueness over the adjacent-edition guard. Existing cast pools support the current league's one appearance per character per edition. This is not unlimited novelty: jokes can recur outside the adjacent-edition horizon. New archives or corrected outcomes may change later selections deterministically. Factual result phrasing, status warnings and machine/Stone Age voice markers may recur; recycled punchlines are the problem.
- Regress actual November 11/12 archive output with aliases/numbers normalized, same-classification cards within an edition, both outcomes for every character, and a third fixture date. Check reruns and reordered sources. Review generated sentences, not just differing template IDs or hashes.

## Curated examples

These are template examples with illustrative labels/margins, **not additional league results**:

- Blowout headline: `[winner] cooks [loser] by [verified margin] — GRONK. The cave mural is mostly one very smug stick figure.` Only the Caveman's verified win can select that premise; other winners have their own pools.
- Commissioner-loss title: `[winner] outpoints The Commissioner — A royal decree meets the shredder.` A narrow result uses `escapes`; a verified smoked result can use `smokes`.
- Standard title: `[winner] outpoints Auto Erik — SYSTEM: Skynet cannot uninstall the result.`
- Close story lead: `[winner] edges [loser] by [verified margin]. Close finish.` Follow with selected character beats, not a demolition claim or another daily-versus-weekly disclaimer.
- Commissioner loss: `Apparently the constitution forgot to award points for being in charge.`
- Caveman win: `UGG. BONK. The Caveman drags the receipt back to the Stone Age. Neanderthal customer service: every complaint gets an extinction event.`
- Caveman loss: `GRONK. The Caveman brought a rock to a Wi-Fi problem. Neanderthal tech support has tried BONK and is all out of ideas.`
- Auto Erik win: `SYSTEM: Skynet online. STATUS: DAILY VICTORY.` An opponent's factory-reset request gets denied.
- Auto Erik loss: `SYSTEM: Skynet malfunction. STATUS: DAILY ERROR. Auto Erik demoted to a toaster.`

Avoid empty filler such as “brought the heat”, “the excuses followed”, or a generic “A vs B” title when there is a verified result and a better punchline. Strong means funny and specific, not a pile of profanity. Do not add new numerical claims to make a joke land.

## Hard boundaries

Roast fictional league characters and actual verified daily results. No private family information, spouses/outsiders, protected-trait attacks, sincere personal abuse, genuine threats, graphic harm, invented real biography, real quotations, history, players, goalies, injuries, lineups, bench/active choices or other unsupported facts. Cartoon body bags, extinction events, roid-movie absurdity and Skynet readouts are metaphors, never real allegations or promises of harm.

## How adapting works

“Learning/adapting” means curating owner-approved examples and feedback here, correcting character beats, and changing deterministic templates with failing-first voice/result regression tests. It does **not** mean model retraining, persistent autonomous learning from images or an inference service running during daily publication. Review the actual generated text, not just the template names. Preserve meaningful history gates and status edge tests when refining humor.

Text-tone approval and image approval are separate. This copy fix has no pending-image dependency and does not change media selection or the current approved IR BOB hat portrait. Newly supplied examples are not blanket publication consent. Use only approved catalog artwork/portraits and retain the existing date/scoreContext correction safeguards. Future unapproved drafts stay private; no-response still means approved fallback art.

This guide changes neither scoring/source schema nor ESPN authentication, aliases, source bundles or scheduling. The **07:00 Arizona** publication target and existing **05:00 review / 05:45 reminder / 06:00 feedback deadline / 06:30 cutoff** stay as documented in [DAILY-FLOW.md](DAILY-FLOW.md). Reviewed text publication can proceed under the owner's explicit instruction; pending images require their own approval. Technical review, exact-source publication and live verification remain separate gates.
