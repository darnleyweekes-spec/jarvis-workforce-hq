from importlib.metadata import version, PackageNotFoundError
import tempfile
import unittest
from pathlib import Path
from alpha_runtime import (SQLiteMissionStore, MissionRequest, Evidence, MissionError,
                           AlphaRuntime, ProposedAction, SpecialistResult,
                           ClaimEvidenceContract)
from semantica_context import SemanticaContext

try:
    version('semantica')
    installed = True
except PackageNotFoundError:
    installed = False

@unittest.skipUnless(installed, 'Install requirements-semantica.txt')
class SemanticaTests(unittest.TestCase):
    def test_projection_is_scoped_rebuildable_and_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SQLiteMissionStore(Path(folder) / 'ledger.sqlite3')
            for mid in ('one', 'two'):
                store.create(MissionRequest('Prepare draft', ['draft'], mission_id=mid))
                store.add_evidence(mid, Evidence('same-id', mid, 'test-source',
                                                '2026-10-06T00:00:00Z', 'hypothesis'))
            before = store.get('one')
            events = store.events('one')
            graph = SemanticaContext(store).build_graph('one')
            self.assertTrue(all(key.startswith('mission:one') for key in graph.nodes))
            evidence = [node for node in graph.nodes.values() if node.node_type == 'evidence']
            self.assertEqual(len(evidence), 1)
            self.assertEqual(evidence[0].metadata['classification'], 'hypothesis')
            self.assertEqual(evidence[0].metadata['source'], 'test-source')
            again = SemanticaContext(store).build_graph('one')
            self.assertEqual(set(graph.nodes), set(again.nodes))
            self.assertEqual(store.get('one'), before)
            self.assertEqual(store.events('one'), events)
            self.assertTrue(store.verify_event_chain('one'))

    def test_invalid_ledger_is_rejected(self):
        class BadStore:
            def verify_event_chain(self, mission_id):
                return False
        with self.assertRaises(MissionError):
            SemanticaContext(BadStore()).build_graph('broken')

    def test_runtime_projection_preserves_approval_and_claim_links(self):
        class Specialist:
            def run(self, task):
                return SpecialistResult(
                    'Draft ready', completed_criteria=('draft',),
                    proposed_actions=(ProposedAction('send', 'email.send', {'body': 'draft'}),),
                    claim_evidence=(ClaimEvidenceContract('draft', 'verified', ('ev',),
                                                         'evidence:source'),))
        with tempfile.TemporaryDirectory() as folder:
            store = SQLiteMissionStore(Path(folder) / 'ledger.sqlite3')
            runtime = AlphaRuntime(store, {'SCRIBE': Specialist()})
            request = MissionRequest('Prepare draft', ['draft'], mission_id='approval')
            runtime.submit(request, 'SCRIBE', [Evidence('ev', 'Draft exists', 'test-source',
                                                       '2026-10-06T00:00:00Z', 'fact')])
            before = store.get('approval')
            self.assertEqual(before['status'], 'AWAITING_APPROVAL')
            graph = runtime.context_graph('approval')
            self.assertIn('mission:approval:claim:0', graph.nodes)
            self.assertIn('mission:approval:verification', graph.nodes)
            self.assertEqual(store.get('approval'), before)
