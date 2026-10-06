import unittest
from alpha_runtime import SpecialistTask,MissionState,MissionError
from local_knowledge_adapter import search_documents
class KnowledgeTests(unittest.TestCase):
    def task(self,allowed=True):
        return SpecialistTask('t','research','search',(),(),('knowledge.local.read',) if allowed else (),(),(),MissionState())
    def test_cited_results(self):
        result=search_documents(self.task(),[{'source':'approved-policy','text':'Staff must approve customer messages.'}],'approve')
        self.assertEqual(result[0]['source'],'approved-policy'); self.assertIn('approve',result[0]['excerpt'])
    def test_permission_and_limits(self):
        with self.assertRaises(MissionError): search_documents(self.task(False),[],'test')
        with self.assertRaises(ValueError): search_documents(self.task(),[],'test',limit=21)
