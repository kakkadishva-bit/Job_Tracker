"""RemoteOK job scraper with enhanced API integration"""

from .base_scraper import BaseScraper
from typing import Optional, Dict, Any, List
from models.job_model import Job
from utils.query_parser import ParsedQuery
import json
import time
import pandas as pd


class RemoteOKScraper(BaseScraper):
    """Enhanced scraper for RemoteOK job board using public API"""
    
    API_URL = "https://remoteok.com/api"
    
    def __init__(self):
        super().__init__()
        self.logger.info("RemoteOKScraper initialized")
    
    def scrape(self, job_title: str, limit: int = 50) -> list:
        """
        Scrape jobs from RemoteOK for a given job title using public API
        
        Args:
            job_title: The job title to search for
            limit: Maximum number of jobs to scrape
            
        Returns:
            List of job dictionaries
        """
        self.logger.info(f"Starting RemoteOK scrape for job title: {job_title}, limit: {limit}")
        jobs = []
        
        try:
            # Fetch all jobs from API
            job_list = self._fetch_jobs_from_api()
            
            if not job_list:
                self.logger.warning("No jobs returned from RemoteOK API")
                return jobs
            
            # Filter and process jobs
            jobs = self._filter_and_process_jobs(job_list, job_title, limit)
            
            self.logger.info(f"Successfully scraped {len(jobs)} jobs from RemoteOK")
            return jobs
            
        except Exception as e:
            self.logger.error(f"Error during RemoteOK scraping: {e}")
            return jobs
    
    def scrape_from_parsed_query(self, parsed_query: ParsedQuery, limit: int = 50) -> list:
        """
        Scrape jobs from RemoteOK using a parsed query object
        
        Args:
            parsed_query: ParsedQuery object with job_title and location
            limit: Maximum number of jobs to scrape
            
        Returns:
            List of job dictionaries
        """
        # Build search query from parsed query
        search_query = self._build_search_query(parsed_query)
        return self.scrape(search_query, limit)
    
    def _fetch_jobs_from_api(self) -> Optional[List[Dict]]:
        """
        Fetch all jobs from RemoteOK API with retry logic
        
        Returns:
            List of job dictionaries or None if failed
        """
        for attempt in range(self.config.retry_attempts):
            try:
                self.logger.debug(f"Fetching RemoteOK API (attempt {attempt + 1})")
                
                response = self.session.get(
                    self.API_URL,
                    timeout=self.config.request_timeout
                )
                response.raise_for_status()
                
                job_list = response.json()
                
                # RemoteOK API returns metadata as first element
                if job_list and isinstance(job_list, list) and len(job_list) > 0:
                    # Skip first element if it's metadata (doesn't have 'position' field)
                    if 'position' not in job_list[0]:
                        job_list = job_list[1:]
                    
                    self.logger.debug(f"Fetched {len(job_list)} jobs from RemoteOK API")
                    return job_list
                
                return []
                
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for RemoteOK API: {e}")
                if attempt < self.config.retry_attempts - 1:
                    time.sleep(self.config.retry_delay)
                else:
                    self.logger.error(f"Failed to fetch RemoteOK API after {self.config.retry_attempts} attempts")
                    return None
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse RemoteOK API response: {e}")
                return None
            except Exception as e:
                self.logger.error(f"Unexpected error fetching RemoteOK API: {e}")
                return None
        
        return None
    
    def _filter_and_process_jobs(self, job_list: List[Dict], search_query: str, limit: int) -> list:
        """
        Filter jobs by search query and process them
        
        Args:
            job_list: List of job dictionaries from API
            search_query: Search query to filter by
            limit: Maximum number of jobs to return
            
        Returns:
            List of processed job dictionaries
        """
        jobs = []
        search_terms = search_query.lower().split()
        
        for job in job_list:
            if len(jobs) >= limit:
                break
            
            try:
                # Extract job data
                job_data = self._extract_job_data(job)
                
                # Filter by search terms (job title, tags, description)
                if self._matches_search_query(job_data, search_terms):
                    # Validate and create job object
                    job_obj = self.create_job_object(job_data)
                    if job_obj:
                        jobs.append(job_obj.to_dict())
                        
            except Exception as e:
                self.logger.warning(f"Error processing job: {e}")
                continue
        
        return jobs
    
    def _matches_search_query(self, job_data: Dict[str, Any], search_terms: List[str]) -> bool:
        """
        Check if job matches search query terms with strict filtering
        
        Args:
            job_data: Job data dictionary
            search_terms: List of search terms
            
        Returns:
            True if job matches search terms
        """
        job_title = job_data.get('job_title', '').lower()
        
        # Strict filtering: at least one search term must be in the job title
        # This prevents irrelevant jobs like "Cleaner" when searching for "python developer"
        title_match = any(term in job_title for term in search_terms if len(term) > 2)
        
        if not title_match:
            return False
        
        # Additional check: ensure job title contains relevant technical terms for developer roles
        # Common irrelevant job titles to filter out
        irrelevant_keywords = ['cleaner', 'baker', 'driver', 'chef', 'waiter', 'receptionist', 
                           'assistant', 'clerk', 'cashier', 'sales', 'marketing', 'hr']
        
        if any(irrelevant in job_title for irrelevant in irrelevant_keywords):
            return False
        
        # For developer/technical roles, ensure some technical relevance
        technical_keywords = ['developer', 'engineer', 'programmer', 'software', 'python', 
                           'java', 'javascript', 'frontend', 'backend', 'fullstack', 'data',
                           'devops', 'architect', 'technical', 'code', 'programming']
        
        # If search terms include technical terms, require at least one in title or tags
        if any(tech in search_terms for tech in technical_keywords):
            tags = ' '.join(job_data.get('tags', [])).lower()
            description = job_data.get('description', '').lower()
            combined_text = f"{job_title} {tags} {description}"
            
            # At least one technical keyword should be present
            has_technical_relevance = any(tech in combined_text for tech in technical_keywords)
            if not has_technical_relevance:
                return False
        
        return True
    
    def _extract_job_data(self, api_job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and normalize job data from RemoteOK API response
        
        Args:
            api_job: Raw job data from API
            
        Returns:
            Normalized job data dictionary
        """
        # Extract salary information
        salary = api_job.get('salary', '')
        if not salary:
            # Try to extract from description or other fields
            salary = 'Not specified'
        
        # Convert epoch to readable date
        posted_date = ''
        epoch = api_job.get('epoch')
        if epoch:
            try:
                import datetime
                posted_date = datetime.datetime.fromtimestamp(epoch).strftime('%Y-%m-%d')
            except Exception:
                posted_date = str(epoch)
        
        # Extract tags
        tags = api_job.get('tags', [])
        tags_str = ', '.join(tags) if tags else ''
        
        # Clean description HTML
        description = api_job.get('description', '')
        description = self.clean_html(description)
        
        # Build description with tags
        if tags_str:
            description = f"{description}\n\nTags: {tags_str}"
        
        return {
            'job_title': api_job.get('position', ''),
            'company_name': api_job.get('company', ''),
            'location': api_job.get('location', 'Remote'),
            'job_url': api_job.get('url', ''),
            'salary': salary,
            'description': description,
            'posted_date': posted_date,
            'source': 'RemoteOK'
        }
    
    def _build_search_query(self, parsed_query: ParsedQuery) -> str:
        """
        Build search query from parsed query object
        
        Args:
            parsed_query: ParsedQuery object
            
        Returns:
            Search query string
        """
        query = parsed_query.job_title
        
        # Add location if present
        if parsed_query.location:
            query = f"{query} {parsed_query.location}"
        
        # Add keywords if present
        if parsed_query.keywords:
            query = f"{query} {' '.join(parsed_query.keywords)}"
        
        return query
if __name__ == "__main__":

    scraper = RemoteOKScraper()

    jobs = scraper.scrape(
        job_title="python developer",
        limit=20
    )

    print(f"\nTotal jobs found: {len(jobs)}\n")

    for job in jobs[:5]:
        print(job)

    if jobs:

        df = pd.DataFrame(jobs)

        file_name = "remoteok_jobs.xlsx"

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