"""
Artist Crawler implementation using Playwright.
Ports logic from AutoCollector's crawler.js
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, Page

from autohelper.shared.logging import get_logger
from autohelper.modules.runner.schemas import ArtifactRef, RunnerProgress
from .base import BaseCollector

logger = get_logger(__name__)


class ArtistCrawler(BaseCollector):
    """
    Crawls artist websites to extract bio and work images.
    """

    async def collect(
        self,
        config: dict[str, Any],
        output_folder: str,
        on_progress: Callable[[RunnerProgress], None] | None,
    ) -> list[ArtifactRef]:
        """
        Run artist crawl.
        
        Config:
            url: Target website URL
        """
        url = config.get("url")
        if not url:
            raise ValueError("URL is required")
            
        if not url.startswith("http"):
            url = "https://" + url

        output_path = Path(output_folder)
        images_dir = output_path / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        artifacts = []
        
        self._report(on_progress, "starting", f"Launching browser for {url}...", 0)

        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            try:
                page = await context.new_page()
                
                # --- Step A: Bio Extraction ---
                self._report(on_progress, "crawling", "Loading home page...", 10)
                await page.goto(url, wait_until="networkidle", timeout=60000)
                
                # Extract Name from Title
                title = await page.title()
                artist_name = title.split('|')[0].split('-')[0].strip() or "Unknown Artist"
                logger.info(f"Scraped Name: {artist_name}")

                # Find About Link
                self._report(on_progress, "crawling", "Looking for Bio...", 20)
                about_url = await self._find_link(page, ['about', 'bio', 'biography', 'cv', 'profile'])
                
                if about_url:
                    logger.info(f"Found About page: {about_url}")
                    await page.goto(about_url, wait_until="networkidle", timeout=30000)
                
                # Extract Bio Text
                bio_text = await self._extract_bio(page)
                logger.info(f"Bio length: {len(bio_text)}")

                # --- Step B: Image Extraction ---
                self._report(on_progress, "crawling", "Looking for Gallery...", 40)
                work_url = await self._find_link(page, ['work', 'portfolio', 'gallery', 'projects'])
                target_gallery = work_url or url
                
                if page.url != target_gallery:
                    logger.info(f"Navigating to Gallery: {target_gallery}")
                    await page.goto(target_gallery, wait_until="networkidle", timeout=30000)

                self._report(on_progress, "crawling", "Extracting images...", 50)
                
                # Scroll to load lazy images
                await self._scroll_page(page)
                
                # Extract image metadata
                works = await self._extract_works(page)
                logger.info(f"Found {len(works)} potential images")

                # --- Step C: Download & Save ---
                self._report(on_progress, "downloading", f"Downloading {len(works)} images...", 70)
                
                saved_works = []
                download_count = 0
                
                for i, work in enumerate(works[:15]):  # Limit to 15 images
                    if not work['src']:
                        continue
                        
                    ext = Path(urlparse(work['src']).path).suffix or '.jpg'
                    if len(ext) > 5: ext = '.jpg'
                    
                    filename = f"web_image_{i+1}{ext}"
                    local_file = images_dir / filename
                    
                    try:
                        # Download image
                        response = await page.request.get(work['src'])
                        if response.status == 200:
                            data = await response.body()
                            local_file.write_bytes(data)
                            
                            saved_works.append({
                                "title": work['title'],
                                "src": f"images/{filename}",
                                "caption_text": work['caption'],
                                "year": ""
                            })
                            
                            artifacts.append(ArtifactRef(
                                ref_id=f"img_{i}",
                                path=str(local_file),
                                artifact_type="image",
                                mime_type=f"image/{ext.lstrip('.')}"
                            ))
                            download_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to download {work['src']}: {e}")

                # Save Metadata JSON
                metadata = {
                    "name": artist_name,
                    "bio": bio_text,
                    "source_url": url,
                    "works": saved_works
                }
                
                metadata_path = output_path / "artist_data.json"
                metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
                
                artifacts.append(ArtifactRef(
                    ref_id="metadata",
                    path=str(metadata_path),
                    artifact_type="json",
                    mime_type="application/json"
                ))

                self._report(on_progress, "complete", f"Downloaded {download_count} images", 100)
                return artifacts

            except Exception as e:
                logger.exception("Crawl failed")
                raise e
            finally:
                await browser.close()

    def _report(self, callback, stage, message, percent):
        """Helper to report progress."""
        if callback:
            callback(RunnerProgress(stage=stage, message=message, percent=percent))

    async def _find_link(self, page: Page, keywords: list[str]) -> str | None:
        """Find a link matching keywords."""
        try:
            # Simple JS evaluation to find link by text
            href = await page.evaluate("""(keywords) => {
                const anchors = Array.from(document.querySelectorAll('a'));
                const match = anchors.find(a => {
                    const text = a.innerText.toLowerCase().trim();
                    return keywords.includes(text);
                });
                return match ? match.href : null;
            }""", keywords)
            return href
        except Exception:
            return None

    async def _extract_bio(self, page: Page) -> str:
        """Extract bio text from page."""
        return await page.evaluate("""() => {
            // Remove junk
            const clones = document.body.cloneNode(true);
            const junk = clones.querySelectorAll('script, style, noscript, svg, form, nav, header, footer, iframe, link');
            junk.forEach(e => e.remove());
            
            // Try paragraphs first
            const ps = Array.from(clones.querySelectorAll('p'));
            const text = ps.map(e => e.innerText).join('\\n\\n');
            
            // Fallback to body text if too short
            return text.length > 200 ? text : clones.innerText;
        }""")

    async def _scroll_page(self, page: Page):
        """Scroll page to trigger lazy loading."""
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await asyncio.sleep(1)
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await asyncio.sleep(1)

    async def _extract_works(self, page: Page) -> list[dict]:
        """Extract image sources and captions."""
        return await page.evaluate("""() => {
            const works = [];
            const processedSrcs = new Set();
            const imgs = Array.from(document.querySelectorAll('img'));
            
            imgs.forEach(img => {
                if (img.width < 300 || img.height < 300) return;
                
                let src = img.src;
                if (img.dataset.src) src = img.dataset.src;
                
                if (!src || !src.startsWith('http')) return;
                if (processedSrcs.has(src)) return;
                processedSrcs.add(src);
                
                let caption = "";
                const fig = img.closest('figure');
                if (fig && fig.querySelector('figcaption')) {
                    caption = fig.querySelector('figcaption').innerText;
                }
                
                works.push({
                    title: img.alt || "Untitled",
                    src: src,
                    caption: caption.trim().replace(/\\n/g, ' | ')
                });
            });
            return works;
        }""")
