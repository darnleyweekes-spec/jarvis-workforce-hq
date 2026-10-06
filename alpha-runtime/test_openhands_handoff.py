import tempfile
import unittest
from pathlib import Path
from alpha_runtime import SQLiteMissionStore, MissionRequest, MissionError
from openhands_handoff import prepare_handoff

class OpenHandsTests(unittest.TestCase):
    def test_handoff_is_scoped_and_does_not_execute_or_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SQLiteMissionStore(Path(folder) / 'ledger.sqlite3')
            for mid in ('selected', 'other'):
                store.create(MissionRequest(mid, ['patch tested'],
                                           allowed_tools=['openhands.prepare'], mission_id=mid))
            before = store.get('selected')
            events = store.events('selected')
            packet = prepare_handoff(store, 'selected', folder)
            self.assertEqual(packet['brief']['objective'], 'selected')
            self.assertTrue(packet['brief']['execution_policy']['dedicated_sandbox_required'])
            self.assertNotIn('other', packet['prompt'])
            self.assertEqual(store.get('selected'), before)
            self.assertEqual(store.events('selected'), events)

    def test_missing_permission_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SQLiteMissionStore(Path(folder) / 'ledger.sqlite3')
            store.create(MissionRequest('Coding', ['patch'], mission_id='blocked'))
            with self.assertRaises(MissionError):
                prepare_handoff(store, 'blocked', folder)

    def test_bad_ledger_rejected(self):
        class BadStore:
            def verify_event_chain(self, mission_id):
                return False
        with self.assertRaises(MissionError):
            prepare_handoff(BadStore(), 'bad', '/')
