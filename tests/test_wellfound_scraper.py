"""Unit tests for Wellfound scraper"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from scrapers.wellfound_scraper import WellfoundScraper
from models.job_model import Job


class TestWellfoundScraper(unittest.TestCase):
    """Test cases for WellfoundScraper"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scraper = WellfoundScraper()
    
    def test_initialization(self):
        """Test scraper initialization"""
        self.assertIsNotNone(self.scraper)
        self.assertEqual(self.scraper.BASE_URL, "https://wellfound.com")
    
    def test_build_search_url(self):
        """Test search URL building"""
        url = self.scraper._build_search_url("Software Engineer")
        self.assertIn("software-engineer", url.lower())
        self.assertIn("wellfound.com", url)
        self.assertIn("role", url)
    
    def test_is_company_line(self):
        """Test company line detection"""
        self.assertTrue(self.scraper._is_company_line("Company: Tech Corp"))
        self.assertTrue(self.scraper._is_company_line("at StartupXYZ"))
        self.assertTrue(self.scraper._is_company_line("by Company Inc"))
        self.assertFalse(self.scraper._is_company_line("Job description here"))
    
    def test_extract_company_name(self):
        """Test company name extraction"""
        self.assertEqual(self.scraper._extract_company_name("Company: Tech Corp"), "Tech Corp")
        self.assertEqual(self.scraper._extract_company_name("at StartupXYZ"), "StartupXYZ")
        self.assertEqual(self.scraper._extract_company_name("by Company Inc"), "Company Inc")
    
    def test_is_location_line(self):
        """Test location line detection"""
        self.assertTrue(self.scraper._is_location_line("Location: Remote"))
        self.assertTrue(self.scraper._is_location_line("based in San Francisco"))
        self.assertTrue(self.scraper._is_location_line("Remote position"))
        self.assertFalse(self.scraper._is_location_line("Job description"))
    
    def test_extract_location(self):
        """Test location extraction"""
        self.assertEqual(self.scraper._extract_location("Location: Remote"), "Remote")
        self.assertEqual(self.scraper._extract_location("based in San Francisco"), "San Francisco")
    
    def test_is_salary_line(self):
        """Test salary line detection"""
        self.assertTrue(self.scraper._is_salary_line("Salary: $100k"))
        self.assertTrue(self.scraper._is_salary_line("Compensation: $120k - $150k"))
        self.assertTrue(self.scraper._is_salary_line("$80k - $100k"))
        self.assertTrue(self.scraper._is_salary_line("Equity: 0.5%"))
        self.assertFalse(self.scraper._is_salary_line("Job description"))
    
    def test_is_url_line(self):
        """Test URL line detection"""
        self.assertTrue(self.scraper._is_url_line("https://example.com/job"))
        self.assertTrue(self.scraper._is_url_line("www.example.com/job"))
        self.assertFalse(self.scraper._is_url_line("Job description"))
    
    def test_extract_url(self):
        """Test URL extraction"""
        self.assertEqual(self.scraper._extract_url("https://example.com/job"), "https://example.com/job")
        self.assertEqual(self.scraper._extract_url("www.example.com/job"), "https://www.example.com/job")
    
    def test_is_metadata_line(self):
        """Test metadata line detection"""
        self.assertTrue(self.scraper._is_metadata_line("Company: Tech Corp"))
        self.assertTrue(self.scraper._is_metadata_line("Location: Remote"))
        self.assertTrue(self.scraper._is_metadata_line("## Job Title"))
        self.assertFalse(self.scraper._is_metadata_line("This is a description"))
    
    def test_split_into_job_sections(self):
        """Test splitting markdown into job sections"""
        markdown = """## Job 1
Company: Tech Corp
Location: Remote

Description here

## Job 2
Company: StartupXYZ
Location: San Francisco

Another description"""
        
        sections = self.scraper._split_into_job_sections(markdown)
        
        self.assertEqual(len(sections), 2)
        self.assertIn("Job 1", sections[0])
        self.assertIn("Job 2", sections[1])
    
    def test_extract_job_from_section(self):
        """Test job data extraction from section"""
        section = """## Software Engineer
Company: Tech Corp
Location: Remote
Salary: $100k
https://example.com/job

This is a great job opportunity for a software engineer."""
        
        job_data = self.scraper._extract_job_from_section(section, "Software Engineer")
        
        self.assertEqual(job_data['job_title'], "Software Engineer")
        self.assertEqual(job_data['company_name'], "Tech Corp")
        self.assertEqual(job_data['location'], "Remote")
        self.assertEqual(job_data['salary'], "$100k")
        self.assertEqual(job_data['job_url'], "https://example.com/job")
        self.assertIn("great job opportunity", job_data['description'])
        self.assertEqual(job_data['source'], "Wellfound")
    
    def test_extract_job_missing_fields(self):
        """Test job extraction with missing fields"""
        section = """## Developer
Some description here"""
        
        job_data = self.scraper._extract_job_from_section(section, "Developer")
        
        self.assertEqual(job_data['job_title'], "Developer")
        self.assertEqual(job_data['company_name'], "")
        self.assertEqual(job_data['location'], "Remote")
        self.assertEqual(job_data['salary'], "Not specified")
    
    @patch('scrapers.wellfound_scraper.WellfoundScraper._scrape_with_firecrawl')
    def test_scrape(self, mock_scrape):
        """Test basic scraping functionality"""
        mock_scrape.return_value = [
            {
                'job_title': 'Software Engineer',
                'company_name': 'Tech Corp',
                'location': 'Remote',
                'job_url': 'https://example.com/job',
                'salary': '$100k',
                'description': 'Great job',
                'posted_date': '',
                'source': 'Wellfound'
            }
        ]
        
        jobs = self.scraper.scrape("Software Engineer", limit=10)
        
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['source'], "Wellfound")
    
    @patch('scrapers.wellfound_scraper.WellfoundScraper._scrape_with_firecrawl')
    def test_scrape_no_firecrawl(self, mock_scrape):
        """Test scraping when Firecrawl is not initialized"""
        self.scraper.app = None
        jobs = self.scraper.scrape("Software Engineer", limit=10)
        
        self.assertEqual(len(jobs), 0)
    
    @patch('scrapers.wellfound_scraper.FirecrawlApp')
    def test_scrape_with_firecrawl_success(self, mock_firecrawl):
        """Test Firecrawl scraping success"""
        # Mock Firecrawl response
        mock_app = Mock()
        mock_app.scrape_url.return_value = {
            'markdown': """## Software Engineer
Company: Tech Corp
Location: Remote
Salary: $100k
https://example.com/job

Great job opportunity"""
        }
        mock_firecrawl.return_value = mock_app
        
        # Reinitialize scraper with mocked Firecrawl
        scraper = WellfoundScraper()
        jobs = scraper.scrape("Software Engineer", limit=10)
        
        self.assertGreater(len(jobs), 0)
    
    @patch('scrapers.wellfound_scraper.FirecrawlApp')
    def test_scrape_with_firecrawl_retry(self, mock_firecrawl):
        """Test Firecrawl retry logic"""
        mock_app = Mock()
        
        # First attempt fails, second succeeds
        mock_app.scrape_url.side_effect = [
            Exception("Network error"),
            {
                'markdown': """## Developer
Company: Startup
Location: Remote

Job description"""
            }
        ]
        mock_firecrawl.return_value = mock_app
        
        scraper = WellfoundScraper()
        jobs = scraper.scrape("Developer", limit=10)
        
        self.assertGreater(len(jobs), 0)


class TestWellfoundScraperIntegration(unittest.TestCase):
    """Integration tests for WellfoundScraper (require Firecrawl API)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scraper = WellfoundScraper()
    
    @unittest.skip("Requires Firecrawl API key - run manually")
    def test_live_firecrawl_scrape(self):
        """Test live Firecrawl scraping"""
        if not self.scraper.app:
            self.skipTest("Firecrawl API key not set")
        
        jobs = self.scraper.scrape("Python", limit=5)
        
        self.assertGreater(len(jobs), 0)
        self.assertLessEqual(len(jobs), 5)
        
        # Validate job structure
        for job in jobs:
            self.assertIn('job_title', job)
            self.assertIn('company_name', job)
            self.assertIn('location', job)
            self.assertEqual(job['source'], 'Wellfound')


if __name__ == '__main__':
    unittest.main()
