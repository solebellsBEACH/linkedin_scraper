"""
Job search scraper for LinkedIn.

Searches for jobs on LinkedIn and extracts job URLs.
"""
import asyncio
import logging
from typing import Optional, List
from urllib.parse import urlencode
from playwright.async_api import Page

from ..callbacks import ProgressCallback, SilentCallback
from .base import BaseScraper

logger = logging.getLogger(__name__)


class JobSearchScraper(BaseScraper):
    """
    Scraper for LinkedIn job search results.
    
    Example:
        async with BrowserManager() as browser:
            scraper = JobSearchScraper(browser.page)
            job_urls = await scraper.search(
                keywords="software engineer",
                location="San Francisco",
                limit=10
            )
    """
    
    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        """
        Initialize job search scraper.
        
        Args:
            page: Playwright page object
            callback: Optional progress callback
        """
        super().__init__(page, callback or SilentCallback())
    
    async def search(
        self,
        keywords: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 25,
        easy_apply: bool = False,
        remote: bool = False,
    ) -> List[str]:
        """
        Search for jobs on LinkedIn.

        Args:
            keywords: Job search keywords (e.g., "software engineer")
            location: Job location (e.g., "San Francisco, CA")
            limit: Maximum number of job URLs to return
            easy_apply: Filter for Easy Apply jobs only
            remote: Filter for remote jobs only

        Returns:
            List of job posting URLs
        """
        logger.info(f"Starting job search: keywords='{keywords}', location='{location}', easy_apply={easy_apply}, remote={remote}")

        search_url = self._build_search_url(keywords, location, easy_apply, remote)
        await self.callback.on_start("JobSearch", search_url)
        
        await self.navigate_and_wait(search_url)
        await self.callback.on_progress("Navigated to search results", 20)

        try:
            await self.page.wait_for_selector('a[href*="/jobs/view/"]', timeout=10000)
        except:
            logger.warning("No job listings found on page")
            return []

        await self.wait_and_focus(1)
        await self._scroll_jobs_list_until(limit)
        await self.callback.on_progress("Loaded job listings", 50)

        job_urls = await self._extract_job_urls(limit)
        await self.callback.on_progress(f"Found {len(job_urls)} job URLs", 90)
        
        await self.callback.on_progress("Search complete", 100)
        await self.callback.on_complete("JobSearch", job_urls)
        
        logger.info(f"Job search complete: found {len(job_urls)} jobs")
        return job_urls
    
    def _build_search_url(
        self,
        keywords: Optional[str] = None,
        location: Optional[str] = None,
        easy_apply: bool = False,
        remote: bool = False,
    ) -> str:
        """Build LinkedIn job search URL with parameters."""
        base_url = "https://www.linkedin.com/jobs/search/"

        params = {}
        if keywords:
            params['keywords'] = keywords
        if location:
            params['location'] = location
        if easy_apply:
            params['f_LF'] = 'f_AL'
        if remote:
            params['f_WT'] = '2'

        if params:
            return f"{base_url}?{urlencode(params)}"
        return base_url
    
    async def _scroll_jobs_list_until(self, limit: int, pause: float = 2.0, max_scrolls: int = 40) -> None:
        """
        Scroll the job list panel until we have enough results or nothing more loads.

        LinkedIn renders job results inside a scrollable sidebar driven by React.
        We locate the scrollable ancestor of a real job link (works regardless of
        class names that LinkedIn A/B tests), then scroll it incrementally and
        dispatch scroll events so React's virtual scroll picks them up.
        """
        # Mark the scrollable ancestor of a real job link — class-name agnostic
        container_found = await self.page.evaluate("""
            () => {
                const link = document.querySelector('a[href*="/jobs/view/"]');
                if (!link) return false;
                let el = link.parentElement;
                while (el && el !== document.body) {
                    const style = window.getComputedStyle(el);
                    const oy = style.overflowY;
                    if ((oy === 'auto' || oy === 'scroll') && el.scrollHeight > el.clientHeight) {
                        el.setAttribute('data-li-scroll', 'jobs-list');
                        return true;
                    }
                    el = el.parentElement;
                }
                return false;
            }
        """)

        logger.info(f"Job list container found via DOM traversal: {container_found}")

        for i in range(max_scrolls):
            current_count = await self.page.locator('a[href*="/jobs/view/"]').count()
            logger.info(f"Scroll {i + 1}: {current_count} jobs so far (limit={limit})")

            if current_count >= limit:
                break

            if container_found:
                await self.page.evaluate("""
                    const el = document.querySelector('[data-li-scroll="jobs-list"]');
                    if (el) {
                        el.scrollTop += 800;
                        el.dispatchEvent(new Event('scroll', { bubbles: true }));
                    }
                """)
            else:
                # Layout with no inner scroll — try keyboard PageDown on the list
                await self.page.keyboard.press("End")

            await asyncio.sleep(pause)

            # Click "See more jobs" button if it appeared
            clicked = await self.page.evaluate("""
                () => {
                    const btn = Array.from(document.querySelectorAll('button')).find(b =>
                        b.textContent.toLowerCase().includes('see more jobs') ||
                        b.textContent.toLowerCase().includes('ver mais vagas') ||
                        b.classList.toString().includes('infinite-scroller__show-more')
                    );
                    if (btn) { btn.click(); return true; }
                    return false;
                }
            """)
            if clicked:
                logger.info("Clicked 'See more jobs' button")
                await asyncio.sleep(pause)

            new_count = await self.page.locator('a[href*="/jobs/view/"]').count()
            if new_count == current_count:
                logger.info(f"No new jobs after scroll {i + 1} — may have reached end of results")
                break

    async def _extract_job_urls(self, limit: int) -> List[str]:
        """
        Extract job URLs from search results.
        
        Args:
            limit: Maximum number of URLs to extract
            
        Returns:
            List of job posting URLs
        """
        job_urls = []
        
        try:
            # Find all job cards/links
            job_links = await self.page.locator('a[href*="/jobs/view/"]').all()
            
            seen_urls = set()
            for link in job_links:
                if len(job_urls) >= limit:
                    break
                
                try:
                    href = await link.get_attribute('href')
                    if href and '/jobs/view/' in href:
                        # Clean URL (remove query params)
                        clean_url = href.split('?')[0] if '?' in href else href
                        
                        # Ensure full URL
                        if not clean_url.startswith('http'):
                            clean_url = f"https://www.linkedin.com{clean_url}"
                        
                        # Avoid duplicates
                        if clean_url not in seen_urls:
                            job_urls.append(clean_url)
                            seen_urls.add(clean_url)
                except Exception as e:
                    logger.debug(f"Error extracting job URL: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Error extracting job URLs: {e}")
        
        return job_urls
