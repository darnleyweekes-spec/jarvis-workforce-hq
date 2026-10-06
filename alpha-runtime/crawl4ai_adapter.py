"""Bounded, read-only Crawl4AI extraction with ALPHA evidence provenance."""
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlsplit
from alpha_runtime import Evidence, MissionError, SpecialistTask

async def extract_page(task: SpecialistTask, url: str, allowed_hosts: tuple[str, ...],
                       crawler=None, max_characters: int = 12000) -> Evidence:
    if 'crawl4ai.read' not in task.allowed_tools:
        raise MissionError('Mission does not permit crawl4ai.read')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in allowed_hosts or parsed.username:
        raise MissionError('URL is outside the approved HTTPS host scope')
    if not 1 <= max_characters <= 50000:
        raise ValueError('Output limit must be between 1 and 50000 characters')
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
    config = CrawlerRunConfig(page_timeout=30000, check_robots_txt=True,
                              word_count_threshold=0)
    if crawler is None:
        async with AsyncWebCrawler(config=BrowserConfig(headless=True)) as owned:
            result = await owned.arun(url=url, config=config)
    else:
        result = await crawler.arun(url=url, config=config)
    if not result.success:
        raise MissionError('Page extraction failed')
    final_url = getattr(result, 'redirected_url', None) or result.url
    if urlsplit(final_url).scheme != 'https' or urlsplit(final_url).hostname not in allowed_hosts:
        raise MissionError('Extraction redirected outside approved scope')
    markdown = result.markdown
    content = markdown.raw_markdown if hasattr(markdown, 'raw_markdown') else str(markdown)
    if not content.strip():
        raise MissionError('Page produced no evidence')
    # The fact recorded is observed page content, not independent proof of its claims.
    return Evidence('crawl-' + sha256((url + content).encode()).hexdigest()[:24],
                    'Observed page content:\n' + content[:max_characters], final_url,
                    datetime.now(timezone.utc).isoformat(), 'fact', 86400)
