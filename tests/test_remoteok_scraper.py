"""Unit tests for RemoteOK scraper"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from scrapers.remoteok_scraper import RemoteOKScraper
from models.job_model import Job


class TestRemoteOKScraper(unittest.TestCase):
    """Test cases for RemoteOKScraper"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scraper = RemoteOKScraper()
    
    def test_initialization(self):
        """Test scraper initialization"""
        self.assertIsNotNone(self.scraper)
        self.assertEqual(self.scraper.API_URL, "https://remoteok.com/api")
    
    @patch('scrapers.remoteok_scraper.RemoteOKScraper._fetch_jobs_from_api')
    def test_scrape(self, mock_fetch):
        """Test basic scraping functionality"""
        # Mock API response
        mock_jobs = [
            {
                'position': 'Software Engineer',
                'company': 'Tech Corp',
                'location': 'Remote',
                'url': 'https://example.com/job1',
                'salary': '$100k',
                'description': 'Great job',
                'epoch': 1234567890,
                'tags': ['python', 'django']
            },
            {
                'position': 'Data Scientist',
                'company': 'Data Inc',
                'location': 'Remote',
                'url': 'https://example.com/job2',
                'salary': '$120k',
                'description': 'Data role',
                'epoch': 1234567891,
                'tags': ['python', 'ml']
            }
        ]
        mock_fetch.return_value = mock_jobs
        
        jobs = self.scraper.scrape("Software Engineer", limit=10)
        
        self.assertGreater(len(jobs), 0)
        self.assertEqual(jobs[0]['source'], 'RemoteOK')
    
    @patch('scrapers.remoteok_scraper.RemoteOKScraper._fetch_jobs_from_api')
    def test_scrape_no_results(self, mock_fetch):
        """Test scraping when no results match"""
        mock_fetch.return_value = [
            {
                'position': 'Marketing Manager',
                'company': 'Marketing Corp',
                'location': 'Remote',
                'url': 'https://example.com/job1',
                'salary': '$80k',
                'description': 'Marketing role',
                'epoch': 1234567890,
                'tags': ['marketing']
            }
        ]
        
        jobs = self.scraper.scrape("Software Engineer", limit=10)
        
        # Should return empty since "Software Engineer" doesn't match "Marketing Manager"
        self.assertEqual(len(jobs), 0)
    
    @patch('scrapers.remoteok_scraper.RemoteOKScraper._fetch_jobs_from_api')
    def test_scrape_api_failure(self, mock_fetch):
        """Test scraping when API fails"""
        mock_fetch.return_value = None
        
        jobs = self.scraper.scrape("Software Engineer", limit=10)
        
        self.assertEqual(len(jobs), 0)
    
    def test_extract_job_data(self):
        """Test job data extraction from API response"""
        api_job = {
            'position': 'Senior Developer',
            'company': 'StartupXYZ',
            'location': 'Remote',
            'url': 'https://remoteok.com/remote-jobs/123',
            'salary': '$150k - $200k',
            'description': 'Senior developer role',
            'epoch': 1234567890,
            'tags': ['senior', 'backend', 'python']
        }
        
        job_data = self.scraper._extract_job_data(api_job)
        
        self.assertEqual(job_data['job_title'], 'Senior Developer')
        self.assertEqual(job_data['company_name'], 'StartupXYZ')
        self.assertEqual(job_data['location'], 'Remote')
        self.assertEqual(job_data['salary'], '$150k - $200k')
        self.assertEqual(job_data['source'], 'RemoteOK')
        self.assertIn('Tags:', job_data['description'])
    
    def test_extract_job_data_missing_fields(self):
        """Test job data extraction with missing fields"""
        api_job = {
            'position': 'Developer',
            'company': 'Company',
            # Missing other fields
        }
        
        job_data = self.scraper._extract_job_data(api_job)
        
        self.assertEqual(job_data['job_title'], 'Developer')
        self.assertEqual(job_data['company_name'], 'Company')
        self.assertEqual(job_data['location'], 'Remote')
        self.assertEqual(job_data['salary'], 'Not specified')
    
    def test_matches_search_query(self):
        """Test search query matching"""
        job_data = {
            'job_title': 'Software Engineer',
            'description': 'Python developer role',
            'tags': ['python', 'django']
        }
        
        # Should match
        self.assertTrue(self.scraper._matches_search_query(job_data, ['software', 'engineer']))
        self.assertTrue(self.scraper._matches_search_query(job_data, ['python']))
        
        # Should not match
        self.assertFalse(self.scraper._matches_search_query(job_data, ['java']))
        self.assertFalse(self.scraper._matches_search_query(job_data, ['marketing']))
    
    def test_build_search_query(self):
        """Test search query building from parsed query"""
        from utils.query_parser import ParsedQuery
        
        parsed_query = ParsedQuery(
            job_title='Software Engineer',
            location='Remote',
            keywords=['python', 'django']
        )
        
        search_query = self.scraper._build_search_query(parsed_query)
        
        self.assertIn('software', search_query.lower())
        self.assertIn('engineer', search_query.lower())
        self.assertIn('remote', search_query.lower())
        self.assertIn('python', search_query.lower())
        self.assertIn('django', search_query.lower())
    
    @patch('scrapers.remoteok_scraper.requests.Session.get')
    def test_fetch_jobs_from_api(self, mock_get):
        """Test API fetching with retry logic"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = [
            {'position': 'Job 1'},
            {'position': 'Job 2'}
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        jobs = self.scraper._fetch_jobs_from_api()
        
        self.assertIsNotNone(jobs)
        self.assertEqual(len(jobs), 2)
    
    @patch('scrapers.remoteok_scraper.requests.Session.get')
    def test_fetch_jobs_with_metadata(self, mock_get):
        """Test API fetching when metadata is present"""
        # Mock response with metadata as first element
        mock_response = Mock()
        mock_response.json.return_value = [
            {'metadata': 'data'},  # Metadata (no 'position' field)
            {'position': 'Job 1'},
            {'position': 'Job 2'}
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        jobs = self.scraper._fetch_jobs_from_api()
        
        # Should skip metadata
        self.assertEqual(len(jobs), 2)
    
    @patch('scrapers.remoteok_scraper.requests.Session.get')
    def test_fetch_jobs_retry_logic(self, mock_get):
        """Test retry logic on API failure"""
        # First attempt fails, second succeeds
        mock_response_fail = Mock()
        mock_response_fail.raise_for_status.side_effect = Exception("Network error")
        
        mock_response_success = Mock()
        mock_response_success.json.return_value = [{'position': 'Job 1'}]
        mock_response_success.raise_for_status = Mock()
        
        mock_get.side_effect = [mock_response_fail, mock_response_success]
        
        jobs = self.scraper._fetch_jobs_from_api()
        
        self.assertIsNotNone(jobs)
        self.assertEqual(len(jobs), 1)


class TestRemoteOKScraperIntegration(unittest.TestCase):
    """Integration tests for RemoteOKScraper (require network access)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scraper = RemoteOKScraper()
    
    @unittest.skip("Requires network access - run manually")
    def test_live_api_fetch(self):
        """Test live API fetch from RemoteOK"""
        jobs = self.scraper._fetch_jobs_from_api()
        
        self.assertIsNotNone(jobs)
        self.assertGreater(len(jobs), 0)
    
    @unittest.skip("Requires network access - run manually")
    def test_live_scrape(self):
        """Test live scraping from RemoteOK"""
        jobs = self.scraper.scrape("Python", limit=5)
        
        self.assertGreater(len(jobs), 0)
        self.assertLessEqual(len(jobs), 5)
        
        # Validate job structure
        for job in jobs:
            self.assertIn('job_title', job)
            self.assertIn('company_name', job)
            self.assertIn('location', job)
            self.assertIn('job_url', job)
            self.assertEqual(job['source'], 'RemoteOK')


if __name__ == '__main__':
    unittest.main()
