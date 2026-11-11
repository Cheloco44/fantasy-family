"""Opt-in ESPN settings access probe; never emits account data."""
import argparse
import json
import os
import sys
from urllib.request import HTTPRedirectHandler, Request, build_opener


URL = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/2027/segments/0/leagues/1399646897?view=mSettings"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main(argv=None, *, environ=None, opener_factory=build_opener):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", action="store_true")
    args = parser.parse_args(argv)
    if not args.network:
        print("Network disabled; pass --network to run the probe.", file=sys.stderr)
        return 2
    try:
        environ = os.environ if environ is None else environ
        headers = {}
        s2, swid = environ.get("ESPN_S2"), environ.get("ESPN_SWID")
        if s2 and swid:
            # Reject header/cookie injection without echoing untrusted values.
            if any(any(ord(c) < 33 or ord(c) > 126 or c in ';,"\\' for c in value)
                   for value in (s2, swid)):
                raise ValueError
            headers["Cookie"] = f"espn_s2={s2}; SWID={swid}"
        request = Request(URL, headers=headers, method="GET")
        with opener_factory(NoRedirect()).open(request, timeout=15) as response:
            if response.status != 200:
                raise ValueError
            body = response.read(1024 * 1024 + 1)
            if len(body) > 1024 * 1024:
                raise ValueError
            data = json.loads(body)
        if not isinstance(data, dict) or data.get("seasonId", 2027) != 2027:
            raise ValueError
        settings = data.get("settings")
        if not isinstance(settings, dict) or not all(
            isinstance(settings.get(key), dict)
            for key in ("scoringSettings", "rosterSettings")
        ):
            raise ValueError
    except Exception:
        # Deliberately sanitize even unexpected library exceptions: they may
        # embed headers, response content, or account identifiers.
        print("Probe failed; access or settings could not be verified.", file=sys.stderr)
        return 1
    print(json.dumps({
        "season": 2027,
        "scoring_settings_present": 1,
        "roster_settings_present": 1,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
