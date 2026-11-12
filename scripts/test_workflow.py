"""Offline workflow contract checks; never load credentials or use network."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class WorkflowTests(unittest.TestCase):
    def test_manual_probe_is_read_only_and_step_scoped(self):
        p = ROOT / '.github/workflows/espn-access-check.yml'
        self.assertTrue(p.exists(), 'Manual access workflow must exist')
        text = p.read_text()
        for required in ['workflow_dispatch:', 'contents: read', 'persist-credentials: false', 'timeout-minutes: 3', "github.ref == 'refs/heads/main'", 'python3 scripts/probe_espn.py --network', '${{ secrets.ESPN_S2 }}', '${{ secrets.ESPN_SWID }}']:
            self.assertIn(required, text)
        for forbidden in ['schedule:', 'pull_request:', 'pull_request_target:', 'push:', 'upload-artifact', 'deploy-pages', 'write-all', 'contents: write', 'set -x']:
            self.assertNotIn(forbidden, text)
        self.assertEqual(text.count('${{ secrets.'), 2)
        self.assertEqual(text.count('env:'), 1)
        self.assertIn('if not os.environ.get', text)
        self.assertIn('11bd71901bbe5b1630ceea73d27597364c9af683', text)

if __name__ == '__main__':
    unittest.main()
