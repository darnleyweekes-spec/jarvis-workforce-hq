import tempfile
import unittest
from pathlib import Path
from alpha_runtime import SQLiteMissionStore, MissionRequest, MissionError
from capability_registry import load_capabilities, prepare_capability

class RegistryTests(unittest.TestCase):
    def test_all_requested_sources_are_pinned(self):
        entries = load_capabilities()
        self.assertEqual(len(entries), 13)
        self.assertIn('python-training', entries)
        self.assertIn('recordly', entries)
        self.assertTrue(all(len(e['commit']) == 40 for e in entries.values()))

    def test_scoped_handoff_cannot_execute_or_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SQLiteMissionStore(Path(folder) / 'ledger.sqlite3')
            store.create(MissionRequest('Extract facts', ['facts supported'],
                                        allowed_tools=['crawl4ai.prepare'], mission_id='m'))
            before = store.get('m')
            packet = prepare_capability(store, 'm', 'crawl4ai')
            self.assertFalse(packet['execution_authorized'])
            self.assertTrue(packet['independent_verification_required'])
            self.assertEqual(packet['success_criteria'], ['facts supported'])
            self.assertEqual(store.get('m'), before)
            with self.assertRaises(MissionError):
                prepare_capability(store, 'm', 'browser-use')
