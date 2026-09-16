# Naukri Scraper Implementation Documentation

## Overview
The Naukri scraper is an HTML-based web scraper that extracts job listings from Naukri.com using BeautifulSoup and requests. It implements robust error handling, pagination support, and multiple CSS selector fallback strategies to handle website structure changes.

## Architecture

### Class Structure
```python
class NaukriScraper(BaseScraper):
    """Enhanced scraper for Naukri.com job board"""
```

The scraper extends the `BaseScraper` class, inheriting common functionality like:
- Retry logic with configurable attempts
- Rate limiting
- Logging integration
- Data validation
- Session management

### Key Components

#### 1. URL Construction
- **Method**: `_build_search_url(job_title: str) -> str`
- **Purpose**: Constructs search URLs for Naukri.com
- **Format**: `https://www.naukri.com/{encoded_job_title}-jobs`
- **Example**: `https://www.naukri.com/software-engineer-jobs`

#### 2. Pagination Handling
- **Method**: `_scrape_with_pagination(base_url: str, limit: int) -> list`
- **Purpose**: Handles multi-page job listing scraping
- **Features**:
  - Automatically detects end of listings
  - Respects job limit across all pages
  - Applies rate limiting between pages
  - Handles page fetch failures gracefully

**Pagination Logic**:
```python
page_url = f"{base_url}-{page}" if page > 1 else base_url
```
- Page 1: `https://www.naukri.com/software-engineer-jobs`
- Page 2: `https://www.naukri.com/software-engineer-jobs-2`
- Page 3: `https://www.naukri.com/software-engineer-jobs-3`

#### 3. Job Element Extraction
- **Method**: `_extract_job_elements(soup) -> list`
- **Purpose**: Identifies job listing elements from HTML
- **Strategy**: Multiple CSS selector fallback
- **Selectors tried**:
  1. `div.jobTuple` (primary)
  2. `div.job-card` (fallback)
  3. `article.job` (fallback)
  4. `div[class*="job"]` (generic fallback)

#### 4. Data Extraction
- **Method**: `_extract_job_data(element) -> Dict[str, Any]`
- **Purpose**: Extracts individual job details from HTML elements
- **Fields extracted**:
  - Job Title
  - Company Name
  - Location
  - Salary
  - Experience (added to description)
  - Posted Date
  - Job Description
  - Job URL
  - Source (always "Naukri")

**Extraction Strategy**:
Each field uses multiple CSS selector fallbacks to handle website structure changes:

```python
title_selectors = [
    ('a', 'title'),           # Primary
    ('a', 'job-title'),       # Fallback 1
    ('h2', 'job-title'),      # Fallback 2
    ('h3', 'job-title')       # Fallback 3
]
```

#### 5. Helper Methods
- **`_extract_text_by_selectors(element, selectors) -> str`**: Extracts text using multiple selector strategies
- **`_extract_url_by_selectors(element, selectors) -> str`**: Extracts URLs and converts relative URLs to absolute
- **`_extract_jobs_from_elements(job_elements, remaining_limit) -> list`**: Processes job elements with validation

## Data Flow

```
User Request (job_title, limit)
    ↓
scrape(job_title, limit)
    ↓
_build_search_url(job_title)
    ↓
_scrape_with_pagination(url, limit)
    ↓
For each page:
    get_soup(page_url) [with retry logic]
    ↓
    _extract_job_elements(soup)
    ↓
    _extract_jobs_from_elements(elements, limit)
    ↓
        For each element:
            _extract_job_data(element)
            ↓
            create_job_object(job_data) [validation]
            ↓
            job.to_dict()
    ↓
    apply_rate_limit()
    ↓
Return list of job dictionaries
```

## Error Handling

### 1. Network Errors
- Handled by base scraper retry logic
- Configurable retry attempts and delays
- Automatic fallback to next page on failure

### 2. HTML Structure Changes
- Multiple CSS selector fallbacks for each field
- Graceful degradation when selectors fail
- Warning logs for missing data

### 3. Data Validation
- Integration with Job model validation
- Invalid jobs are filtered out
- Missing required fields logged as warnings

### 4. Pagination Edge Cases
- Detects end of listings (fewer jobs than expected)
- Handles empty pages
- Respects overall job limit

## Configuration

The scraper uses configuration from `config.py`:

```python
# Rate limiting
RATE_LIMIT_DELAY = 1.0  # seconds between requests

# Retry logic
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2  # seconds

# Request timeout
REQUEST_TIMEOUT = 10  # seconds
```

## Testing

### Unit Tests
Located in `tests/test_naukri_scraper.py`:

1. **Test Initialization**: Verifies scraper setup
2. **Test URL Building**: Validates search URL construction
3. **Test Text Extraction**: Tests selector fallback logic
4. **Test URL Extraction**: Tests URL handling (relative/absolute)
5. **Test Job Data Extraction**: Tests complete data extraction
6. **Test Pagination**: Tests multi-page scraping logic
7. **Test Error Handling**: Tests failure scenarios

### Running Tests
```bash
# Run all tests
python -m pytest tests/test_naukri_scraper.py

# Run with coverage
python -m pytest tests/test_naukri_scraper.py --cov=scrapers.naukri_scraper

# Run specific test
python -m pytest tests/test_naukri_scraper.py::TestNaukriScraper::test_build_search_url
```

### Integration Tests
Integration tests require network access and are skipped by default:
```bash
# Run integration tests
python -m pytest tests/test_naukri_scraper.py::TestNaukriScraperIntegration --no-skip
```

## Performance Characteristics

### Scraping Speed
- Approximately 1-2 seconds per page (including rate limiting)
- 20 jobs per page (Naukri standard)
- 50 jobs = ~3 pages = ~3-6 seconds

### Resource Usage
- Memory: Minimal (processes one page at a time)
- Network: 1 request per page + rate limiting delay
- CPU: Low (HTML parsing is efficient)

### Rate Limiting
- Default: 1 second delay between pages
- Configurable via `RATE_LIMIT_DELAY`
- Prevents IP blocking from Naukri

## Anti-Scraping Measures

### Implemented
- User-Agent header (standard browser)
- Rate limiting between requests
- Session reuse (connection pooling)
- Retry logic with exponential backoff

### Potential Issues
- IP blocking after excessive requests
- CAPTCHA challenges
- Website structure changes
- Session timeouts

### Mitigation Strategies
- Use reasonable rate limits
- Monitor for blocking responses
- Update selectors when structure changes
- Consider proxy rotation for large-scale scraping

## Maintenance

### Updating Selectors
If Naukri changes their HTML structure:

1. Inspect the new HTML structure using browser DevTools
2. Identify new CSS selectors for job elements
3. Update selector lists in `_extract_job_data()`
4. Add new fallback selectors
5. Test with sample job searches

### Common Issues

**Issue**: No jobs found
- **Solution**: Check if selectors need updating, verify URL format

**Issue**: Missing job fields
- **Solution**: Add more fallback selectors for missing fields

**Issue**: Pagination not working
- **Solution**: Check if pagination URL format has changed

**Issue**: Rate limiting/blocking
- **Solution**: Increase `RATE_LIMIT_DELAY`, reduce concurrent requests

## Usage Example

```python
from scrapers.naukri_scraper import NaukriScraper

# Initialize scraper
scraper = NaukriScraper()

# Scrape jobs
jobs = scraper.scrape("Software Engineer", limit=50)

# Process results
for job in jobs:
    print(f"{job['job_title']} at {job['company_name']}")
    print(f"Location: {job['location']}")
    print(f"Salary: {job['salary']}")
    print(f"URL: {job['job_url']}")
    print("---")
```

## Data Format

Each job dictionary contains:
```python
{
    'job_title': str,        # Job title
    'company_name': str,     # Company name
    'location': str,         # Job location
    'job_url': str,          # Absolute URL to job posting
    'salary': str,           # Salary information or "Not specified"
    'description': str,      # Job description (may include experience)
    'posted_date': str,      # Posting date
    'source': 'Naukri'       # Always "Naukri"
}
```

## Dependencies

- `requests`: HTTP library
- `beautifulsoup4`: HTML parsing
- `lxml`: XML/HTML parser
- `models.job_model`: Data validation
- `utils.logger`: Logging
- `config`: Configuration management

## Future Enhancements

1. **Advanced Filtering**: Add filters for location, experience, salary range
2. **Caching**: Implement caching to reduce redundant requests
3. **Headless Browser**: Use Selenium for JavaScript-rendered content
4. **Proxy Rotation**: Add proxy support for large-scale scraping
5. **Distributed Scraping**: Support concurrent scraping across multiple IPs

## References

- Naukri.com: https://www.naukri.com/
- BeautifulSoup Documentation: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- Requests Documentation: https://requests.readthedocs.io/
