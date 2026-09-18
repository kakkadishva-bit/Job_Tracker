"""Naukri job scraper with enhanced features"""

import pandas as pd
from .base_scraper import BaseScraper
from urllib.parse import quote, urljoin
from typing import Optional, Dict, Any
from models.job_model import Job
from utils.query_parser import ParsedQuery


class NaukriScraper(BaseScraper):
    """Enhanced scraper for Naukri.com job board with pagination and robust error handling"""
    
    BASE_URL = "https://www.naukri.com"
    
    def __init__(self):
        super().__init__()
        self.logger.info("NaukriScraper initialized")
    
    def scrape(self, job_title: str, limit: int = 50, location: Optional[str] = None) -> list:
        """
        Scrape jobs from Naukri for a given job title with pagination support
        
        Args:
            job_title: The job title to search for
            limit: Maximum number of jobs to scrape
            location: Optional location filter (e.g., "Bangalore")
            
        Returns:
            List of job dictionaries
        """
        self.logger.info(f"Starting Naukri scrape for job title: {job_title}, location: {location}, limit: {limit}")
        jobs = []
        
        try:
            # Build search URL
            search_url = self._build_search_url(job_title, location)
            self.logger.debug(f"Search URL: {search_url}")
            
            # Scrape with pagination
            jobs = self._scrape_with_pagination(search_url, limit)
            
            self.logger.info(f"Successfully scraped {len(jobs)} jobs from Naukri")
            return jobs
            
        except Exception as e:
            self.logger.error(f"Error during Naukri scraping: {e}")
            return jobs
    
    def scrape_from_parsed_query(self, parsed_query: ParsedQuery, limit: int = 50) -> list:
        """
        Scrape jobs from Naukri using a parsed query object
        
        Args:
            parsed_query: ParsedQuery object with job_title and location
            limit: Maximum number of jobs to scrape
            
        Returns:
            List of job dictionaries
        """
        return self.scrape(
            job_title=parsed_query.job_title,
            limit=limit,
            location=parsed_query.location
        )
    
    def _build_search_url(self, job_title: str, location: Optional[str] = None) -> str:
        """
        Build search URL for Naukri with optional location filter
        
        Args:
            job_title: The job title to search for
            location: Optional location filter
            
        Returns:
            Complete search URL
        """
        encoded_title = quote(job_title.strip().lower().replace(" ", "-"))
        
        if location:
            encoded_location = quote(location)
            return f"{self.BASE_URL}/{encoded_title}-jobs-in-{encoded_location}"
        else:
            return f"{self.BASE_URL}/{encoded_title}-jobs"
    
    def _scrape_with_pagination(self, base_url: str, limit: int) -> list:
        """
        Scrape jobs with pagination support
        
        Args:
            base_url: Base search URL
            limit: Maximum number of jobs to scrape
            
        Returns:
            List of job dictionaries
        """
        jobs = []
        page = 1
        jobs_per_page = 20  # Naukri typically shows 20 jobs per page
        
        while len(jobs) < limit:
            self.logger.debug(f"Scraping page {page}")
            
            # Build paginated URL
            page_url = f"{base_url}-{page}" if page > 1 else base_url
            
            # Get page content 
            soup = self.get_dynamic_soup(page_url)
            if not soup:
                self.logger.warning(f"Failed to fetch page {page}")
                break
            #DEBUGGING
            print("\n" + "=" * 50)
            print("PAGE URL:", page_url)
            if soup.title:
                print("PAGE TITLE:", soup.title.text)
            else:
                print("PAGE TITLE: No title")
            with open("debug_naukri.html", "w", encoding="utf-8") as f:
                f.write(str(soup))
            print("Saved HTML to debug_naukri.html")
            print("=" * 50)
            
            # Extract job elements
            job_elements = self._extract_job_elements(soup)
            
            if not job_elements:
                self.logger.info(f"No more jobs found on page {page}")
                break
            
            # Extract data from job elements
            page_jobs = self._extract_jobs_from_elements(job_elements, limit - len(jobs))
            jobs.extend(page_jobs)
            
            self.logger.debug(f"Found {len(page_jobs)} jobs on page {page}, total: {len(jobs)}")
            
            # Check if we've reached the limit
            if len(jobs) >= limit:
                break
            
            # Check if we've exhausted all pages
            if len(page_jobs) < jobs_per_page:
                self.logger.info("Reached end of job listings")
                break
            
            page += 1
            self.apply_rate_limit()
        
        return jobs
    
    def _extract_job_elements(self, soup) -> list:
        """
        Extract job elements from page HTML with updated selectors for current Naukri structure
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            List of job element tags
        """
        # Updated selectors for current Naukri HTML structure (2026)
        selectors = [
            ('div', 'srp-jobtuple-wrapper'),  # Current Naukri structure
            ('div', 'jobTuple'),               # Legacy structure
            ('article', 'job'),                # Article-based structure
            ('div', 'job-card'),               # Card-based structure
            ('div', lambda x: x and 'job' in x.lower())  # Any div with 'job' in class
        ]
        
        for tag, class_name in selectors:
            if callable(class_name):
                elements = soup.find_all(tag, class_=class_name)
            else:
                elements = soup.find_all(tag, class_=class_name)
            
            if elements:
                self.logger.debug(f"Found {len(elements)} job elements using selector: {tag}.{class_name if not callable(class_name) else 'lambda'}")
                return elements
        
        # Fallback: try to find any div with href links (job listings usually have links)
        all_divs = soup.find_all('div')
        job_divs = [div for div in all_divs if div.find('a', href=True)]
        if job_divs:
            self.logger.debug(f"Found {len(job_divs)} potential job elements using fallback link detection")
            return job_divs
        
        self.logger.warning("No job elements found with any selector")
        return []
    
    def _extract_jobs_from_elements(self, job_elements: list, remaining_limit: int) -> list:
        """
        Extract job data from job elements
        
        Args:
            job_elements: List of job element tags
            remaining_limit: Maximum number of jobs to extract from this batch
            
        Returns:
            List of job dictionaries
        """
        jobs = []
        
        for element in job_elements[:remaining_limit]:
            try:
                job_data = self._extract_job_data(element)
                
                # Validate and create job object
                job = self.create_job_object(job_data)
                if job:
                    jobs.append(job.to_dict())
                    
            except Exception as e:
                self.logger.warning(f"Error extracting job data from element: {e}")
                continue
        
        return jobs
    
    def _extract_job_data(self, element) -> Dict[str, Any]:
        """
        Extract job data from a single job element with updated selectors for current Naukri structure
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            Dictionary with job data
        """
        job_data = {}
        
        # Job title and URL - updated selectors for current Naukri structure
        title_selectors = [
            ('a', 'title'),
            ('a', 'srp-job-title'),
            ('h2', 'job-title'),
            ('h3', 'job-title'),
            ('a', lambda x: x and 'title' in x.lower())  # Any link with 'title' in class
        ]
        
        job_data['job_title'] = self._extract_text_by_selectors(element, title_selectors)
        job_data['job_url'] = self._extract_url_by_selectors(element, title_selectors)
        
        # Company name - updated selectors
        company_selectors = [
            ('a', 'comp-name'),
            ('span', 'comp-name'),
            ('a', 'subTitle'),
            ('a', 'company-name'),
            ('div', 'companyName'),
            ('span', 'companyName'),
            ('a', lambda x: x and 'company' in x.lower()),
        ]
        
        job_data['company_name'] = self._extract_text_by_selectors(element, company_selectors)
        
        # Location - updated selectors
        location_selectors = [
            ('li', 'location'),
            ('span', 'location'),
            ('div', 'location'),
            ('p', 'location'),
            ('span', 'locWdth'),
            ('div', lambda x: x and 'location' in x.lower())
        ]
        
        job_data['location'] = self._extract_text_by_selectors(element, location_selectors)
        
        # Salary - updated selectors
        salary_selectors = [
            ('li', 'salary'),
            ('span', 'salary'),
            ('div', 'salary'),
            ('p', 'salary'),
            ('span', 'salary-tag'),
            ('div', lambda x: x and 'salary' in x.lower())
        ]
        
        job_data['salary'] = self._extract_text_by_selectors(element, salary_selectors) or 'Not specified'
        
        # Experience (optional, can be added to description)
        exp_selectors = [
            ('li', 'experience'),
            ('span', 'experience'),
            ('div', 'experience'),
            ('span', 'exp-tag'),
            ('div', lambda x: x and 'experience' in x.lower())
        ]
        
        experience = self._extract_text_by_selectors(element, exp_selectors)
        
        # Posted date - updated selectors
        posted_selectors = [
            ('div', 'jobTupleFooter'),
            ('span', 'posted-date'),
            ('div', 'posted'),
            ('p', 'posted'),
            ('span', 'job-post'),
            ('div', lambda x: x and 'posted' in x.lower())
        ]
        
        job_data['posted_date'] = self._extract_text_by_selectors(element, posted_selectors)
        
        # Description - updated selectors
        desc_selectors = [
            ('div', 'job-description'),
            ('div', 'description'),
            ('p', 'description'),
            ('span', 'description'),
            ('div', 'job-desc'),
            ('div', lambda x: x and 'description' in x.lower())
        ]
        
        description = self._extract_text_by_selectors(element, desc_selectors)
        
        # Combine experience with description if available
        if experience:
            job_data['description'] = f"Experience: {experience}\n{description}" if description else experience
        else:
            job_data['description'] = description
        
        job_data['source'] = 'Naukri'
        
        return job_data
    
    def _extract_text_by_selectors(self, element, selectors: list) -> str:
        """
        Extract text using multiple selector strategies
        
        Args:
            element: BeautifulSoup element
            selectors: List of (tag, class) tuples
            
        Returns:
            Extracted text or empty string
        """
        for tag, class_name in selectors:
            try:
                found = element.find(tag, class_=class_name)
                if found:
                    text = found.text.strip()
                    if text:
                        return text
            except Exception:
                continue
        
        return ''
    
    def _extract_url_by_selectors(self, element, selectors: list) -> str:
        """
        Extract URL using multiple selector strategies
        
        Args:
            element: BeautifulSoup element
            selectors: List of (tag, class) tuples
            
        Returns:
            Extracted URL or empty string
        """
        for tag, class_name in selectors:
            try:
                found = element.find(tag, class_=class_name)
                if found and found.get('href'):
                    url = found.get('href')
                    # Ensure absolute URL
                    url = urljoin(self.BASE_URL, url)
                    return url
            except Exception:
                continue
        
        return ''
if __name__ == "__main__":

    scraper = NaukriScraper()

    jobs = scraper.scrape(
        job_title="python developer",
        limit=50,
        location="Bangalore"
    )

    print(f"\nTotal jobs found: {len(jobs)}\n")

    if jobs:

        df = pd.DataFrame(jobs)

        file_name = "naukri_jobs.xlsx"

        df.to_excel(
            file_name,
            index=False
        )

        print(
            f"Saved {len(jobs)} jobs "
            f"to {file_name}"
        )

    else:
        print("No jobs found.")