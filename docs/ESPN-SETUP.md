# ESPN access probe — not a recap generator

## Status and scope

- League: `1399646897`; ESPN season year: `2027` (2026–27).
- A prior public, unauthenticated settings request returned **HTTP 401**. Live integration is **not complete**. No authenticated access, response schema, scoring interpretation, or recap pipeline has been verified against ESPN by this implementation.
- This is a single-request, read-only **access probe**, not recap generation. It does not write league data, enumerate members, persist responses, or enable automation.
- Python 3 standard library only; no dependencies or `.env` file needed.

The only target is a GET to:

```text
https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/2027/segments/0/leagues/1399646897?view=mSettings
```

The URL is fixed in code, TLS verification uses Python defaults, redirects are refused (including same-host redirects), and the request has a 15-second socket timeout with a 1 MiB response limit. No retry loop is configured. Cookies are attached only when **both** nonempty `ESPN_S2` and `ESPN_SWID` exist in the probe process environment. Otherwise the request is unauthenticated; partial cookies are not sent. Invalid cookie characters are rejected without echoing values.

## Offline checks (safe default)

From `/home/marcelo/projects/possum-busters`:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p test_probe.py -v
python3 scripts/probe_espn.py
```

Tests use synthetic response/error fixtures and injected openers; no ESPN traffic or real credentials. The second command refuses network access and exits `2`. Only the explicit `--network` flag permits a request. Do not run a live probe as part of tests.

## Optional authorized manual check over SSH

Perform this only when the account owner authorizes live access. Use a trusted host and verified SSH host key. Obtain your own `espn_s2` and `SWID` cookie values through your authenticated browser's cookie inspector; never share cookies in chat, tickets, screenshots, logs, or this repository.

**Account cookies may grant broader account access even though this client only performs a read-only GET.** They are not league-scoped read-only API keys. Prefer an appropriately limited account where possible; follow ESPN's terms and revoke/rotate exposed or obsolete sessions.

First open an interactive SSH terminal to your trusted host (replace `your-trusted-host`):

```sh
ssh -t your-trusted-host
```

On that host, run the following literal script. Paste secret values **only into the hidden getpass prompts**, never into commands. It sets the host Python process environment, then invokes the probe as a subprocess inheriting that environment; no cookie values are passed in argv or printed. The heredoc contains code only, not credentials. No `.env`, secret file, shell export with literal values, git change, or SSH environment forwarding is needed.

```sh
cd /home/marcelo/projects/possum-busters
set +x
ulimit -c 0
python3 - <<'PY'
import getpass
import os
import subprocess
import sys
import warnings

# Fail rather than fall back to an echoing prompt without a controlling tty.
warnings.simplefilter('error', getpass.GetPassWarning)
try:
    os.environ['ESPN_S2'] = getpass.getpass('ESPN_S2 (hidden): ')
    os.environ['ESPN_SWID'] = getpass.getpass('ESPN_SWID (hidden): ')
    if not os.environ['ESPN_S2'] or not os.environ['ESPN_SWID']:
        print('Both cookies are required for this authenticated check.', file=sys.stderr)
        result = 2
    else:
        result = subprocess.run(
            [sys.executable, 'scripts/probe_espn.py', '--network'],
            check=False,
        ).returncode
except (getpass.GetPassWarning, EOFError, KeyboardInterrupt):
    print('Secure prompt unavailable or cancelled.', file=sys.stderr)
    result = 2
finally:
    os.environ.pop('ESPN_S2', None)
    os.environ.pop('ESPN_SWID', None)
raise SystemExit(result)
PY
```

Use a private terminal without session recording, shell/terminal debugging, environment dumps, or shared access. Getpass prevents normal terminal echo/history storage; it does not protect against a compromised host, privileged users, same-user process inspection, or external input recording. Environment and response data exist transiently in process memory; cleanup is not a guarantee of memory zeroization. Close the session when finished. Never run `env`, `printenv`, header dumps, HTTP debug logging, or traceback diagnostics with live cookies loaded.

## Results and limitations

Exit `0` means HTTP 200 with object-shaped scoring and roster settings. The only success output is numeric JSON:

```json
{"season":2027,"scoring_settings_present":1,"roster_settings_present":1}
```

The season is the fixed requested season; if ESPN supplies `seasonId`, a mismatch fails. Presence means object-shaped fields, not that rules have been interpreted or validated. No member records, names, raw setting strings, headers, cookies, or raw responses are printed.

Exit `1` means access or settings could not be verified: HTTP 401, other HTTP errors, redirects, timeouts, malformed/oversized JSON, or missing/wrong-shaped scoring or roster settings all fail closed with the same generic message. This intentionally does not expose exception detail. A failure does not prove that cookies alone are the issue: season availability, authorization, and API/schema changes remain possible blockers. Exit `2` covers lack of network opt-in or CLI usage errors. Do not infer live integration success from offline tests.

## Manual GitHub Actions access check

Marcelo approved the demo source and this manual workflow for `Cheloco44/fantasy-family`. The owner reports adding repository Actions secrets `ESPN_S2` and `ESPN_SWID`; no secret values are retrieved by the assistant.

After the reviewed workflow is pushed to `main`, open **Actions → ESPN read-only access check → Run workflow**, select `main`, and run it. The assistant may dispatch this approved check if its GitHub token has Actions write permission. Otherwise the owner can use that button without sharing or broadening credentials.

The workflow accepts manual dispatch only, restricts execution to this repository's `main`, grants `contents: read`, pins checkout to a verified commit, and disables persisted Git credentials. Offline tests run without ESPN secrets; only the final fixed-GET probe step receives the two secrets. Missing secrets fail the step. No raw API payload, credentials, cache, artifact, site data or summary is uploaded. The probe prints only its sanitized numeric success summary or generic error.

A green workflow establishes settings access from the runner only. It does not validate scoring rules, historical lineups, the daily recap, website deployment, or a scheduler. Workflow status and the actual run ID must be read back before reporting success. Logs in this public repository may be publicly visible; never add raw settings or debugging output to this job.

## Future daily pipeline — disabled

A future daily target of **05:00 America/Phoenix = 12:00 UTC** could use an Actions UTC cron of `0 12 * * *`. GitHub Actions scheduled runs can be delayed (or missed); this is a target, not an exact delivery guarantee. Any future implementation needs explicit authorization, protected secret handling, minimal permissions, data minimization, and independently verified league/scoring mapping before recap generation. No scheduler, website deployment, actual league-data publication, or recap generator is enabled. The manual-only access-check workflow described above is the sole automation currently implemented.
