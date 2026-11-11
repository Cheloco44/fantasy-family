"""Offline-only tests: all network paths use a synthetic opener."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import build_opener


SPEC = importlib.util.spec_from_file_location(
    "probe_espn", Path(__file__).with_name("probe_espn.py")
)
probe = None
if SPEC and SPEC.origin and Path(SPEC.origin).exists():
    probe = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(probe)


class ProbeTests(unittest.TestCase):
    def invoke(self, payload, environ=None, status=200):
        self.requests = []
        self.handlers = []
        class Response(io.BytesIO):
            pass
        class Opener:
            def open(inner, request, timeout):
                self.requests.append((request, timeout))
                if isinstance(payload, Exception):
                    raise payload
                response = Response(payload)
                response.status = status
                return response
        def factory(*handlers):
            self.handlers.extend(handlers)
            return Opener()
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = probe.main(["--network"], environ=environ or {}, opener_factory=factory)
        return result, output.getvalue()

    def test_success_is_fixed_get_with_numeric_summary_only(self):
        payload = b'{"seasonId":2027,"settings":{"scoringSettings":{"secret":"private"},"rosterSettings":{"secret":"private"}},"members":[{"name":"PRIVATE MEMBER"}]}'
        result, output = self.invoke(payload, {"ESPN_S2": "FAKE_S2", "ESPN_SWID": "FAKE_SWID"})
        self.assertEqual(result, 0)
        self.assertEqual(output, '{"season":2027,"scoring_settings_present":1,"roster_settings_present":1}\n')
        self.assertEqual(len(self.requests), 1)
        request, timeout = self.requests[0]
        self.assertEqual(request.full_url, "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/2027/segments/0/leagues/1399646897?view=mSettings")
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertGreater(timeout, 0)
        self.assertEqual(request.get_header("Cookie"), "espn_s2=FAKE_S2; SWID=FAKE_SWID")
        self.assertEqual(len(self.handlers), 1)
        self.assertIsNone(self.handlers[0].redirect_request(request, None, 302, "Found", {}, "https://example.invalid/"))

    def test_errors_fail_closed_without_leaking_cookie_or_response(self):
        secret = "FAKE_COOKIE_NEVER_LOG"
        cases = [
            HTTPError("https://example.invalid/" + secret, 401, secret, {}, io.BytesIO(secret.encode())),
            HTTPError("https://example.invalid/", 302, secret, {}, None),
            URLError(secret), TimeoutError(secret), RuntimeError(secret),
            secret.encode(), b'{}', b'[]', b'{"settings":null}',
            b'{"settings":{"scoringSettings":{},"rosterSettings":null}}',
            b'{"settings":{"scoringSettings":"private","rosterSettings":{}}}',
            b'{"seasonId":2026,"settings":{"scoringSettings":{},"rosterSettings":{}}}',
            b' ' * (1024 * 1024 + 1),
        ]
        for payload in cases:
            with self.subTest(kind=type(payload).__name__):
                result, output = self.invoke(payload, {"ESPN_S2": secret, "ESPN_SWID": secret})
                self.assertNotEqual(result, 0)
                self.assertEqual(output, "Probe failed; access or settings could not be verified.\n")
        for status in (301, 302, 307, 308, 401, 500):
            with self.subTest(status=status):
                result, output = self.invoke(b'{"settings":{"scoringSettings":{},"rosterSettings":{}}}', status=status)
                self.assertNotEqual(result, 0)
                self.assertNotIn(secret, output)

    def test_partial_cookies_are_never_sent(self):
        for environ in ({}, {"ESPN_S2": "FAKE"}, {"ESPN_SWID": "FAKE"}, {"ESPN_S2": "FAKE", "ESPN_SWID": ""}):
            with self.subTest(keys=tuple(environ)):
                result, _ = self.invoke(b'{"settings":{"scoringSettings":{},"rosterSettings":{}}}', environ)
                self.assertEqual(result, 0)
                self.assertIsNone(self.requests[0][0].get_header("Cookie"))

    def test_unsafe_cookie_values_fail_before_opening(self):
        for unsafe in ("FAKE\r\nInjected: yes", "FAKE; other=value", "FAKE\x00", "FAKE\u2603", "FAKE value"):
            result, output = self.invoke(b'{}', {"ESPN_S2": unsafe, "ESPN_SWID": "FAKE"})
            self.assertNotEqual(result, 0)
            self.assertEqual(self.requests, [])
            self.assertEqual(output, "Probe failed; access or settings could not be verified.\n")

    def test_real_opener_has_only_our_redirect_handler(self):
        opener = build_opener(probe.NoRedirect())
        redirects = [h for h in opener.handlers if isinstance(h, probe.HTTPRedirectHandler)]
        self.assertEqual(len(redirects), 1)
        self.assertIsInstance(redirects[0], probe.NoRedirect)
        for code in (301, 302, 303, 307, 308):
            self.assertIsNone(redirects[0].redirect_request(None, None, code, "", {}, "https://example.invalid/"))

    def test_network_requires_explicit_opt_in(self):
        self.assertIsNotNone(probe, "probe implementation is missing")
        def forbidden(*args):
            self.fail("network opener created without --network")
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = probe.main([], environ={}, opener_factory=forbidden)
        self.assertNotEqual(result, 0)
        self.assertEqual(output.getvalue(), "Network disabled; pass --network to run the probe.\n")


if __name__ == "__main__":
    unittest.main()
