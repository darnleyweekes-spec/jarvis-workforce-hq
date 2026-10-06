from importlib.metadata import version, PackageNotFoundError
from types import SimpleNamespace
import unittest
from alpha_runtime import MissionState, SpecialistTask, MissionError
from crawl4ai_adapter import extract_page
try:
    version('crawl4ai')
    installed = True
except PackageNotFoundError:
    installed = False

@unittest.skipUnless(installed, 'Install the pinned Crawl4AI environment')
class CrawlerTests(unittest.IsolatedAsyncioTestCase):
    def task(self, allowed=True):
        return SpecialistTask('task', 'SCOUT', 'Read page', ('facts',), (),
                              ('crawl4ai.read',) if allowed else (), (), (), MissionState())

    async def test_bounded_source_evidence(self):
        class Crawler:
            async def arun(self, **kwargs):
                return SimpleNamespace(success=True,url=kwargs['url'],
                                       markdown='Observed text '*100)
        result = await extract_page(self.task(), 'https://example.test/page',
                                    ('example.test',), crawler=Crawler(), max_characters=20)
        self.assertEqual(result.source, 'https://example.test/page')
        self.assertEqual(result.classification, 'fact')
        self.assertTrue(result.retrieved_at)
        self.assertEqual(len(result.claim.split('\n', 1)[1]), 20)

    async def test_denies_unscoped_or_unpermitted_pages(self):
        with self.assertRaises(MissionError):
            await extract_page(self.task(False), 'https://example.test', ('example.test',))
        with self.assertRaises(MissionError):
            await extract_page(self.task(), 'https://outside.test', ('example.test',))
