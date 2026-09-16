"""Wellfound job scraper using Firecrawl (markdown parsing method)"""

import os
import re
import time
from typing import Dict, List
from urllib.parse import quote

from .base_scraper import BaseScraper
from utils.query_parser import ParsedQuery
from dotenv import load_dotenv

try:
    from firecrawl import FirecrawlApp
except Exception:
    FirecrawlApp = None  # type: ignore

load_dotenv()


class WellfoundScraper(BaseScraper):
    """Scraper for Wellfound job board using Firecrawl."""

    BASE_URL = "https://wellfound.com"

    def __init__(self):
        super().__init__()
        api_key = os.environ.get("FIRECRAWL_API_KEY")
        self.app = None
        if FirecrawlApp is not None:
            try:
                if api_key:
                    self.app = FirecrawlApp(api_key=api_key)
                else:
                    try:
                        self.app = FirecrawlApp()
                    except TypeError:
                        try:
                            self.app = FirecrawlApp(api_key="dummy-test-key")
                        except Exception as err:
                            self.logger.error("Firecrawl init failed: %s", err)
                    except Exception as err:
                        self.logger.error("Firecrawl init failed: %s", err)
            except Exception as err:
                self.logger.error("Firecrawl init failed: %s", err)

    def _build_search_url(self, job_title: str) -> str:
        slug = quote(job_title.strip().lower().replace(" ", "-"))
        return self.BASE_URL + "/role/" + slug

    def _is_company_line(self, line: str) -> bool:
        if not line or not line.strip():
            return False
        low = line.strip().lower()
        if low.startswith("company:"):
            return True
        if low.startswith("at ") and len(line.strip()) > 3:
            return True
        if low.startswith("by ") and len(line.strip()) > 3:
            return True
        return "startup" in low or "company" in low

    def _extract_company_name(self, line: str) -> str:
        text = (line or "").strip()
        low = text.lower()
        if low.startswith("company:"):
            return text.split(":", 1)[1].strip()
        if low.startswith("at ") or low.startswith("by "):
            return text[3:].strip()
        return text

    def _is_location_line(self, line: str) -> bool:
        if not line or not line.strip():
            return False
        low = line.strip().lower()
        if low.startswith("location:"):
            return True
        if "based in" in low:
            return True
        if "remote" in low:
            return True
        if "office" in low:
            return True
        return "location" in low

    def _is_salary_line(self, line: str) -> bool:
        if not line or not line.strip():
            return False
        low = line.strip().lower()
        if "salary" in low:
            return True
        if "compensation" in low:
            return True
        if low.startswith("pay:"):
            return True
        if "equity" in low:
            return True
        if "stock" in low:
            return True
        return "$" in line

    def _extract_salary(self, line: str) -> str:
        text = (line or "").strip()
        if ":" in text:
            prefix, _, rest = text.partition(":")
            ok = ("salary", "compensation", "pay", "equity", "stock")
            if prefix.strip().lower() in ok and rest.strip():
                return rest.strip()
        return text

    def _is_url_line(self, line: str) -> bool:
        if not line or not line.strip():
            return False
        low = line.strip().lower()
        if low.startswith("http://"):
            return True
        if low.startswith("https://"):
            return True
        return low.startswith("www.")

    def _extract_url(self, line: str) -> str:
        text = (line or "").strip()
        low = text.lower()
        if low.startswith("http://") or low.startswith("https://"):
            return text
        if low.startswith("www."):
            return "https://" + text
        return text

    def _is_metadata_line(self, line: str) -> bool:
        if not line or not line.strip():
            return False
        if re.match(r"^#{1,6}\s+\S", line.strip()):
            return True
        if self._is_company_line(line):
            return True
        if self._is_location_line(line):
            return True
        if self._is_salary_line(line):
            return True
        return self._is_url_line(line)

    def _split_into_job_sections(self, markdown_content: str) -> List[str]:
        if not markdown_content or not markdown_content.strip():
            return []
        lines = markdown_content.split("\n")
        sections: List[str] = []
        current: List[str] = []
        for line in lines:
            s = line.strip()
            if re.match(r"^#{1,3}\s+\S", s):
                if current and any(x.strip() for x in current):
                    sections.append("\n".join(current).strip())
                current = [line]
            else:
                current.append(line)
        if current and any(x.strip() for x in current):
            sections.append("\n".join(current).strip())
        sections = [x for x in sections if x.strip()]
        if sections:
            return sections
        return [markdown_content.strip()]

    def _extract_location(self, line: str) -> str:
        text = (line or "").strip()
        low = text.lower()
        if low.startswith("location:"):
            return text.split(":", 1)[1].strip()
        if "based in" in low:
            idx = low.find("based in")
            return text[idx + 8:].strip(" :-.")
        return text

    def _extract_job_from_section(self, section: str, job_title: str) -> Dict:
        title = (job_title or "").strip()
        company = ""
        location = "Remote"
        salary = "Not specified"
        job_url = ""
        desc: List[str] = []
        if section and section.strip():
            for raw in section.split("\n"):
                line = raw.strip()
                if not line:
                    continue
                m = re.match(r"^#{1,3}\s+(.*)$", line)
                if m and m.group(1).strip():
                    if title == (job_title or "").strip() or not title:
                        title = m.group(1).strip()
                    continue
                if self._is_url_line(line) and not job_url:
                    job_url = self._extract_url(line)
                    continue
                if self._is_company_line(line) and not company:
                    company = self._extract_company_name(line) or company
                    continue
                if self._is_location_line(line) and location == "Remote":
                    location = self._extract_location(line) or location
                    continue
                if self._is_salary_line(line) and salary == "Not specified":
                    salary = self._extract_salary(line) or salary
                    continue
                if self._is_metadata_line(line):
                    continue
                desc.append(line)
        return {
            "job_title": title or "Unknown Role",
            "company_name": company,
            "location": location,
            "job_url": job_url,
            "salary": salary,
            "description": " ".join(desc).strip(),
            "posted_date": "",
            "source": "Wellfound",
        }

    def scrape_from_parsed_query(self, parsed_query: ParsedQuery, limit: int = 50) -> list:
        return self.scrape(parsed_query.job_title, limit)

    def _get_markdown_from_response(self, response) -> str:
        if not response:
            return ""
        if isinstance(response, dict):
            md = response.get("markdown")
            if isinstance(md, str) and md.strip():
                return md
            data = response.get("data")
            if isinstance(data, dict) and isinstance(data.get("markdown"), str):
                return data["markdown"]
            return ""
        markdown = getattr(response, "markdown", None)
        if isinstance(markdown, str) and markdown.strip():
            return markdown
        return ""

    def _parse_markdown_jobs(self, md: str, job_title: str, limit: int = 50) -> List[Dict]:
        if not md or not md.strip():
            return []
        jobs: List[Dict] = []
        for section in self._split_into_job_sections(md):
            if len(jobs) >= limit:
                break
            jobs.append(self._extract_job_from_section(section, job_title))
        return jobs[:limit]

    def _scrape_with_firecrawl(self, url: str, jt: str, limit: int = 50) -> List[Dict]:
        if not self.app:
            self.logger.warning("Firecrawl not initialized - skipping scrape")
            return []
        params = {"formats": ["markdown"], "onlyMainContent": True}
        last_error = None
        for attempt in range(1, 4):
            try:
                try:
                    response = self.app.scrape_url(url, params=params)
                except TypeError:
                    response = self.app.scrape_url(url, formats=["markdown"])
                markdown = self._get_markdown_from_response(response)
                if not markdown or not markdown.strip():
                    last_error = "empty markdown response"
                    self.logger.warning("Firecrawl empty response %d", attempt)
                    time.sleep(1)
                    continue
                return self._parse_markdown_jobs(markdown, jt, limit)
            except Exception as err:
                last_error = err
                self.logger.warning("Firecrawl attempt %d failed: %s", attempt, err)
                if attempt < 3:
                    time.sleep(2)
        self.logger.error("Firecrawl failed for %s: %s", url, last_error)
        return []

    def scrape(self, job_title: str, limit: int = 50) -> list:
        if not self.app:
            self.logger.warning("Firecrawl not initialized - returning no jobs")
            return []
        try:
            url = self._build_search_url(job_title)
            self.logger.info("Scraping Wellfound: %s", url)
            return self._scrape_with_firecrawl(url, job_title, limit)
        except Exception as err:
            self.logger.error("Wellfound scrape failed: %s", err)
            return []

