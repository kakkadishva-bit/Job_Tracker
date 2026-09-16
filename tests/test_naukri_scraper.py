"""Unit tests for Naukri scraper"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from bs4 import BeautifulSoup
from scrapers.naukri_scraper import NaukriScraper
from models.job_model import Job


class TestNaukriScraper(unittest.TestCase):
    """Test cases for NaukriScraper"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scraper = NaukriScraper()
    
    def test_initialization(self):
        """Test scraper initialization"""
        self.assertIsNotNone(self.scraper)
        self.assertEqual(self.scraper.BASE_URL, "https://www.naukri.com")
    
    def test_build_search_url(self):
        """Test search URL building"""
        url = self.scraper._build_search_url("Software Engineer")
        self.assertIn("software-engineer", url.lower())
        self.assertIn("naukri.com", url)
        self.assertIn("jobs", url)
    
    def test_extract_text_by_selectors(self):
        """Test text extraction with multiple selectors"""
        # Create mock element
        mock_element = Mock()
        mock_tag = Mock()
        mock_tag.text = "Test Title"
        mock_element.find = Mock(return_value=mock_tag)
        
        selectors = [('a', 'title'), ('h2', 'job-title')]
        result = self.scraper._extract_text_by_selectors(mock_element, selectors)
        
        self.assertEqual(result, "Test Title")
    
    def test_extract_text_by_selectors_no_match(self):
        """Test text extraction when no selectors match"""
        mock_element = Mock()
        mock_element.find = Mock(return_value=None)
        
        selectors = [('a', 'title'), ('h2', 'job-title')]
        result = self.scraper._extract_text_by_selectors(mock_element, selectors)
        
        self.assertEqual(result, '')
    
    def test_extract_url_by_selectors(self):
        """Test URL extraction with multiple selectors"""
        mock_element = Mock()
        mock_tag = Mock()
        mock_tag.get = Mock(return_value='/job/test')
        mock_element.find = Mock(return_value=mock_tag)
        
        selectors = [('a', 'title'), ('h2', 'job-title')]
        result = self.scraper._extract_url_by_selectors(mock_element, selectors)
        
        self.assertEqual(result, "https://www.naukri.com/job/test")
    
    def test_extract_url_by_selectors_absolute(self):
        """Test URL extraction with absolute URL"""
        mock_element = Mock()
        mock_tag = Mock()
        mock_tag.get = Mock(return_value='https://example.com/job')
        mock_element.find = Mock(return_value=mock_tag)
        
        selectors = [('a', 'title')]
        result = self.scraper._extract_url_by_selectors(mock_element, selectors)
        
        self.assertEqual(result, "https://example.com/job")
    
    def test_extract_job_data(self):
        """Test job data extraction from element"""
        # Create a mock element with nested structure
        mock_element = Mock()
        
        # Mock the find method to return different results based on class name
        def mock_find(tag, class_=None):
            mock_result = Mock()
            if class_ == 'title':
                mock_result.text = "Software Engineer"
                mock_result.get = Mock(return_value='/job/123')
            elif class_ == 'subTitle':
                mock_result.text = "Tech Company"
            elif class_ == 'location':
                mock_result.text = "Bangalore"
            elif class_ == 'salary':
                mock_result.text = "10-15 LPA"
            elif class_ == 'experience':
                mock_result.text = "3-5 years"
            elif class_ == 'jobTupleFooter':
                mock_result.text = "2 days ago"
            elif class_ == 'job-description':
                mock_result.text = "Job description here"
            else:
                return None
            return mock_result
        
        mock_element.find = mock_find
        
        job_data = self.scraper._extract_job_data(mock_element)
        
        self.assertEqual(job_data['job_title'], "Software Engineer")
        self.assertEqual(job_data['company_name'], "Tech Company")
        self.assertEqual(job_data['location'], "Bangalore")
        self.assertEqual(job_data['salary'], "10-15 LPA")
        self.assertEqual(job_data['source'], "Naukri")
        self.assertIn("Experience", job_data['description'])
    
    @patch('scrapers.naukri_scraper.NaukriScraper.get_soup')
    def test_scrape_with_pagination(self, mock_get_soup):
        """Test scraping with pagination"""
        # Create mock soup with job elements
        mock_soup = Mock()
        mock_elements = [Mock(), Mock(), Mock()]
        mock_soup.find_all = Mock(return_value=mock_elements)
        mock_get_soup.return_value = mock_soup
        
        # Mock job extraction
        with patch.object(self.scraper, '_extract_job_elements', return_value=mock_elements):
            with patch.object(self.scraper, '_extract_jobs_from_elements', return_value=[
                {'job_title': 'Job 1', 'company_name': 'Company 1', 'location': 'Location 1',
                 'job_url': 'http://example.com/job1', 'salary': '10 LPA', 'description': 'Desc',
                 'posted_date': '1 day ago', 'source': 'Naukri'}
            ]):
                jobs = self.scraper._scrape_with_pagination("http://example.com/jobs", 10)
        
        self.assertGreater(len(jobs), 0)
    
    @patch('scrapers.naukri_scraper.NaukriScraper.get_soup')
    def test_scrape_with_pagination_no_results(self, mock_get_soup):
        """Test scraping when no results are found"""
        mock_soup = Mock()
        mock_soup.find_all = Mock(return_value=[])
        mock_get_soup.return_value = mock_soup
        
        with patch.object(self.scraper, '_extract_job_elements', return_value=[]):
            jobs = self.scraper._scrape_with_pagination("http://example.com/jobs", 10)
        
        self.assertEqual(len(jobs), 0)
    
    @patch('scrapers.naukri_scraper.NaukriScraper.get_soup')
    def test_scrape_with_pagination_failure(self, mock_get_soup):
        """Test scraping when page fetch fails"""
        mock_get_soup.return_value = None
        
        jobs = self.scraper._scrape_with_pagination("http://example.com/jobs", 10)
        
        self.assertEqual(len(jobs), 0)
    
    def test_extract_job_elements(self):
        """Test job element extraction from soup"""
        mock_soup = Mock()
        mock_elements = [Mock(), Mock()]
        mock_soup.find_all = Mock(return_value=mock_elements)
        
        elements = self.scraper._extract_job_elements(mock_soup)
        
        self.assertEqual(len(elements), 2)
    
    def test_extract_job_elements_no_results(self):
        """Test job element extraction when no elements found"""
        mock_soup = Mock()
        mock_soup.find_all = Mock(return_value=[])
        
        elements = self.scraper._extract_job_elements(mock_soup)
        
        self.assertEqual(len(elements), 0)


class TestNaukriScraperIntegration(unittest.TestCase):
    """Integration tests for NaukriScraper (require network access)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scraper = NaukriScraper()
    
    @unittest.skip("Requires network access - run manually")
    def test_live_scrape(self):
        """Test live scraping from Naukri"""
        jobs = self.scraper.scrape("Python Developer", limit=5)
        
        self.assertGreater(len(jobs), 0)
        self.assertLessEqual(len(jobs), 5)
        
        # Validate job structure
        for job in jobs:
            self.assertIn('job_title', job)
            self.assertIn('company_name', job)
            self.assertIn('location', job)
            self.assertIn('job_url', job)
            self.assertEqual(job['source'], 'Naukri')


if __name__ == '__main__':
    unittest.main()
