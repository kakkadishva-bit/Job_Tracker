"""Base scraper class for job boards"""

from abc import ABC, abstractmethod
import requests
from bs4 import BeautifulSoup
import time
import re
from typing import Optional, Dict, Any

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from utils.logger import get_logger
from config import config
from models.job_model import Job, JobValidator


class BaseScraper(ABC):
    """Base class for job board scrapers with common functionality"""

    def __init__(self):
        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        })

        self.logger = get_logger()
        self.config = config
        self.driver = None

    @abstractmethod
    def scrape(self, job_title: str, limit: int = 50) -> list:
        """
        Scrape jobs for a given job title
        """
        pass

    def get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """
        Get BeautifulSoup object using requests
        """

        for attempt in range(self.config.retry_attempts):

            try:
                self.logger.debug(
                    f"Fetching URL: {url} "
                    f"(attempt {attempt + 1})"
                )

                response = self.session.get(
                    url,
                    timeout=self.config.request_timeout
                )

                response.raise_for_status()

                time.sleep(
                    self.config.rate_limit_delay
                )

                return BeautifulSoup(
                    response.content,
                    "lxml"
                )

            except requests.exceptions.RequestException as e:

                self.logger.warning(
                    f"Attempt {attempt + 1} "
                    f"failed for {url}: {e}"
                )

                if attempt < self.config.retry_attempts - 1:
                    time.sleep(
                        self.config.retry_delay
                    )

                else:
                    self.logger.error(
                        f"Failed to fetch {url}"
                    )
                    return None

            except Exception as e:
                self.logger.error(
                    f"Unexpected error: {e}"
                )
                return None

        return None

    def get_dynamic_soup(
        self,
        url: str
    ) -> Optional[BeautifulSoup]:
        """
        Use Selenium for dynamic websites
        like Naukri or LinkedIn
        """

        try:

            if not self.driver:

                chrome_options = Options()

                chrome_options.add_argument(
                    "--start-maximized"
                )

                chrome_options.add_argument(
                    "--disable-blink-features=AutomationControlled"
                )

                self.driver = webdriver.Chrome(
                    service=Service(
                        ChromeDriverManager().install()
                    ),
                    options=chrome_options
                )

            self.logger.info(
                f"Opening browser: {url}"
            )

            self.driver.get(url)

            time.sleep(5)

            html = self.driver.page_source

            return BeautifulSoup(
                html,
                "lxml"
            )

        except Exception as e:

            self.logger.error(
                f"Selenium fetch failed: {e}"
            )

            return None

    def normalize_job_data(
        self,
        job_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Normalize job data
        """

        sanitized = JobValidator.sanitize(
            job_data
        )

        is_valid, errors = (
            JobValidator.validate(
                sanitized
            )
        )

        if not is_valid:
            self.logger.warning(
                f"Job validation failed: {errors}"
            )

        return {
            "job_title":
            sanitized.get(
                "job_title", ""
            ),

            "company_name":
            sanitized.get(
                "company_name", ""
            ),

            "location":
            sanitized.get(
                "location", ""
            ),

            "job_url":
            sanitized.get(
                "job_url", ""
            ),

            "salary":
            sanitized.get(
                "salary",
                "Not specified"
            ),

            "description":
            sanitized.get(
                "description", ""
            ),

            "posted_date":
            sanitized.get(
                "posted_date", ""
            ),

            "source":
            sanitized.get(
                "source", ""
            )
        }

    def create_job_object(
        self,
        job_data: Dict[str, Any]
    ) -> Optional[Job]:

        try:
            normalized = (
                self.normalize_job_data(
                    job_data
                )
            )

            job = Job.from_dict(
                normalized
            )

            if job.is_valid():
                return job

            self.logger.warning(
                f"Invalid job data: "
                f"{job.job_title}"
            )

            return None

        except Exception as e:
            self.logger.error(
                f"Error creating job object: {e}"
            )
            return None

    def apply_rate_limit(self):
        time.sleep(
            self.config.rate_limit_delay
        )

    def clean_html(
        self,
        html_content: str
    ) -> str:

        if not html_content:
            return ""

        soup = BeautifulSoup(
            html_content,
            "lxml"
        )

        text = soup.get_text()

        text = re.sub(
            r"\s+",
            " ",
            text
        ).strip()

        text = (
            text.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
        )

        return text