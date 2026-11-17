"""Run from repository root: python -m unittest discover -s tests -v"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from monitoring import HistoryStore, MonitorMixin
from translations import LANGUAGES, translate


class HistoryTests(unittest.TestCase):
    def test_baseline_and_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            store = HistoryStore(Path(temp) / 'db.sqlite3')
            first = {'192.168.1.2': SimpleNamespace(ip='192.168.1.2', mac='AA:BB', latency_ms=15.0)}
            changes, baseline = store.record_scan('192.168.1.0/24', first, 4.2)
            self.assertEqual(changes, [])
            self.assertFalse(baseline)
            second = {'192.168.1.3': SimpleNamespace(ip='192.168.1.3', mac='CC:DD', latency_ms=8.0)}
            changes, baseline = store.record_scan('192.168.1.0/24', second, 3.4)
            self.assertTrue(baseline)
            self.assertEqual([item[:2] for item in changes], [('new', '192.168.1.3'), ('missing', '192.168.1.2')])
            self.assertEqual(len(store.events()), 2)
            self.assertEqual(len(store.scans()), 2)
            # Independent baselines for different private subnets.
            changes, baseline = store.record_scan('10.1.1.0/24', first, 2)
            self.assertFalse(baseline)
            self.assertEqual(changes, [])
            store.clear()
            self.assertEqual(store.events(), [])
            self.assertEqual(store.scans(), [])

    def test_localization(self):
        for lang in LANGUAGES:
            self.assertNotEqual(translate(lang, 'monitor'), 'monitor')
            self.assertIn('30', translate(lang, 'interval_error'))
            self.assertIn('192.168.1.0/24', translate(lang, 'monitor_permission', network='192.168.1.0/24', interval=60))

    def test_rate_format(self):
        self.assertEqual(MonitorMixin.human_rate(2048), '2.0 KB/s')


if __name__ == '__main__':
    unittest.main()
