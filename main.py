"""
Job Agent - Main Entry Point
Scrapes jobs from Naukri, RemoteOK, and Wellfound based on job role and location
"""

from scrapers.naukri_scraper import NaukriScraper
from scrapers.remoteok_scraper import RemoteOKScraper
from scrapers.wellfound_scraper import WellfoundScraper
from storage.csv_storage import CSVStorage
from utils.logger import get_logger
import argparse
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()


def _matches_job_role(job: dict, job_role: str) -> bool:
    """
    Check if job matches the searched role
    
    Args:
        job: Job dictionary
        job_role: Job role to match against
        
    Returns:
        True if job matches the role
    """
    job_title = job.get('job_title', '').lower()
    job_role_lower = job_role.lower()
    
    # Check if job role is in job title
    if job_role_lower in job_title:
        return True
    
    # Check for partial matches (e.g., "python" matches "python developer")
    role_words = job_role_lower.split()
    return any(word in job_title for word in role_words if len(word) > 2)


def main():
    parser = argparse.ArgumentParser(
        description='Job Agent - Scrape jobs from multiple platforms',
        epilog='Example: python main.py --job-role "Software Engineer" --location "Bangalore"'
    )
    parser.add_argument('--job-role', type=str, required=True, help='Job role to search for (e.g., "Software Engineer")')
    parser.add_argument('--location', type=str, default='', help='Location filter (e.g., "Bangalore", "Remote")')
    parser.add_argument('--output', type=str, default='jobs.csv', help='Output CSV file name')
    parser.add_argument('--limit', type=int, default=50, help='Number of jobs per platform')
    parser.add_argument('--cache-html', action='store_true', help='Enable HTML caching for offline scraping')
    parser.add_argument('--save-html', action='store_true', help='Save HTML pages for debugging')
    
    args = parser.parse_args()
    
    logger = get_logger()
    logger.info(f"Job Agent started - Job Role: {args.job_role}, Location: {args.location}")
    
    print(f"Job Role: {args.job_role}")
    if args.location:
        print(f"Location: {args.location}")
    else:
        print("Location: Not specified (searching all locations)")
    
    print(f"Limit per platform: {args.limit}")
    print(f"Output file: {args.output}")
    print("-" * 50)
    
    all_jobs = []
    
    # Scrape from Naukri
    print("Scraping Naukri...")
    naukri_scraper = NaukriScraper()
    naukri_jobs = naukri_scraper.scrape(args.job_role, limit=args.limit, location=args.location if args.location else None)
    # Filter jobs by role relevance
    naukri_jobs = [job for job in naukri_jobs if _matches_job_role(job, args.job_role)]
    all_jobs.extend(naukri_jobs)
    print(f"Found {len(naukri_jobs)} jobs from Naukri")
    
    # Scrape from RemoteOK
    print("Scraping RemoteOK...")
    remoteok_scraper = RemoteOKScraper()
    # Use job role only for RemoteOK (location filtering not supported by API)
    remoteok_jobs = remoteok_scraper.scrape(args.job_role, limit=args.limit)
    # Filter jobs by role relevance
    remoteok_jobs = [job for job in remoteok_jobs if _matches_job_role(job, args.job_role)]
    all_jobs.extend(remoteok_jobs)
    print(f"Found {len(remoteok_jobs)} jobs from RemoteOK")
    
    # Scrape from Wellfound
    print("Scraping Wellfound...")
    wellfound_scraper = WellfoundScraper()
    wellfound_jobs = wellfound_scraper.scrape(args.job_role, limit=args.limit)
    # Filter jobs by role relevance
    wellfound_jobs = [job for job in wellfound_jobs if _matches_job_role(job, args.job_role)]
    all_jobs.extend(wellfound_jobs)
    print(f"Found {len(wellfound_jobs)} jobs from Wellfound")
    
    # Store in CSV
    print("-" * 50)
    print(f"Total jobs found: {len(all_jobs)}")
    
    storage = CSVStorage()
    storage.save_to_csv(all_jobs, args.output)
    print(f"Jobs saved to {args.output}")
    
    logger.info(f"Job Agent completed. Total jobs: {len(all_jobs)}")


if __name__ == "__main__":
    main()
