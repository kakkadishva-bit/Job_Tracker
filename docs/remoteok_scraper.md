# RemoteOK Scraper Implementation Documentation

## Overview
The RemoteOK scraper uses the public RemoteOK API to fetch job listings. It implements robust error handling, retry logic, and intelligent search filtering to match job queries.

## Architecture

### Class Structure
```python
class RemoteOKScraper(BaseScraper):
    """Enhanced scraper for RemoteOK job board using public API"""
```

The scraper extends the `BaseScraper` class, inheriting common functionality like:
- Retry logic with configurable attempts
- Rate limiting
- Logging integration
- Data validation
- Session management

### Key Components

#### 1. API Integration
- **Method**: `_fetch_jobs_from_api() -> Optional[List[Dict]]`
- **Purpose**: Fetches all jobs from RemoteOK public API
- **API Endpoint**: `https://remoteok.com/api`
- **Features**:
  - Automatic retry logic on failures
  - JSON parsing with error handling
  - Metadata filtering (skips first element if it's metadata)
  - Configurable timeout and retry attempts

**API Response Format**:
```json
[
  {"metadata": "data"},  // First element may be metadata
  {
    "position": "Software Engineer",
    "company": "Tech Corp",
    "location": "Remote",
    "url": "https://example.com/job",
    "salary": "$100k",
    "description": "Job description",
    "epoch": 1234567890,
    "tags": ["python", "django"]
  }
]
```

#### 2. Search Query Processing
- **Method**: `scrape(job_title: str, limit: int) -> list`
- **Purpose**: Main scraping method with search filtering
- **Features**:
  - Fetches all jobs from API
  - Filters jobs by search terms
  - Processes and validates job data
  - Respects job limit

**Search Logic**:
- Splits search query into terms
- Checks if all terms match in job title, description, or tags
- Case-insensitive matching
- Supports multi-term queries (e.g., "python django")

#### 3. Data Extraction
- **Method**: `_extract_job_data(api_job: Dict) -> Dict`
- **Purpose**: Extracts and normalizes job data from API response
- **Features**:
  - Converts epoch timestamps to readable dates
  - Extracts and formats tags
  - Handles missing fields gracefully
  - Normalizes salary information

**Data Mapping**:
```python
{
    'job_title': api_job['position'],
    'company_name': api_job['company'],
    'location': api_job['location'] or 'Remote',
    'job_url': api_job['url'],
    'salary': api_job['salary'] or 'Not specified',
    'description': api_job['description'] + tags,
    'posted_date': converted_epoch,
    'source': 'RemoteOK'
}
```

#### 4. Query Matching
- **Method**: `_matches_search_query(job_data: Dict, search_terms: List) -> bool`
- **Purpose**: Checks if job matches search query terms
- **Features**:
  - Searches across job title, description, and tags
  - All terms must match (AND logic)
  - Case-insensitive matching

#### 5. Parsed Query Support
- **Method**: `scrape_from_parsed_query(parsed_query: ParsedQuery, limit: int) -> list`
- **Purpose**: Supports natural language query parsing
- **Features**:
  - Integrates with QueryParser
  - Builds search query from parsed components
  - Includes location and keywords in search

## Data Flow

```
User Request (job_title, limit)
    ↓
scrape(job_title, limit)
    ↓
_fetch_jobs_from_api()
    ↓
For each attempt (retry logic):
    GET https://remoteok.com/api
    ↓
    Parse JSON response
    ↓
    Filter metadata (first element)
    ↓
    Return job list
    ↓
_filter_and_process_jobs(job_list, search_query, limit)
    ↓
For each job:
    _extract_job_data(job)
    ↓
    _matches_search_query(job_data, search_terms)
    ↓
    create_job_object(job_data) [validation]
    ↓
    job.to_dict()
    ↓
Return list of job dictionaries
```

## Error Handling

### 1. API Failures
- **Network Errors**: Retry with exponential backoff
- **JSON Parse Errors**: Log and return None
- **Timeout Errors**: Configurable timeout with retry
- **HTTP Errors**: Raise exception and retry

### 2. Data Validation
- Integration with Job model validation
- Invalid jobs are filtered out
- Missing required fields logged as warnings
- Graceful handling of missing optional fields

### 3. Search Failures
- Empty API responses handled gracefully
- No matching jobs returns empty list
- Invalid search terms don't crash scraper

## Configuration

The scraper uses configuration from `config.py`:

```python
# Retry logic
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2  # seconds

# Request timeout
REQUEST_TIMEOUT = 10  # seconds
```

## Testing

### Unit Tests
Located in `tests/test_remoteok_scraper.py`:

1. **Test Initialization**: Verifies scraper setup
2. **Test Basic Scraping**: Tests job fetching and filtering
3. **Test No Results**: Tests handling of empty results
4. **Test API Failure**: Tests error handling
5. **Test Data Extraction**: Tests job data extraction
6. **Test Missing Fields**: Tests handling of incomplete data
7. **Test Search Matching**: Tests query matching logic
8. **Test Query Building**: Tests parsed query support
9. **Test API Fetching**: Tests API call with retry logic
10. **Test Metadata Handling**: Tests metadata filtering
11. **Test Retry Logic**: Tests retry on failure

### Running Tests
```bash
# Run all tests
python -m pytest tests/test_remoteok_scraper.py

# Run with coverage
python -m pytest tests/test_remoteok_scraper.py --cov=scrapers.remoteok_scraper

# Run specific test
python -m pytest tests/test_remoteok_scraper.py::TestRemoteOKScraper::test_extract_job_data
```

### Integration Tests
Integration tests require network access and are skipped by default:
```bash
# Run integration tests
python -m pytest tests/test_remoteok_scraper.py::TestRemoteOKScraperIntegration --no-skip
```

## Performance Characteristics

### API Performance
- Single API call fetches all jobs (~100-200 jobs)
- No pagination needed (API returns all jobs)
- Fast response time (~1-2 seconds)
- No rate limiting required (public API)

### Filtering Performance
- In-memory filtering of job list
- Fast string matching
- O(n) complexity where n = total jobs
- Typically < 100ms for filtering

### Resource Usage
- Memory: Low (processes one job at a time)
- Network: 1 API call per scrape
- CPU: Low (string matching is efficient)

## API Details

### Endpoint
- **URL**: `https://remoteok.com/api`
- **Method**: GET
- **Authentication**: None required
- **Rate Limit**: None specified (be reasonable)

### Response Structure
- **Format**: JSON array
- **First Element**: Often metadata (no 'position' field)
- **Job Elements**: Objects with job details
- **Update Frequency**: Real-time

### Key Fields
- `position`: Job title
- `company`: Company name
- `location`: Job location (usually "Remote")
- `url`: Job posting URL
- `salary`: Salary information
- `description`: Job description
- `epoch`: Posting timestamp (Unix epoch)
- `tags`: Array of skill tags

## Usage Example

```python
from scrapers.remoteok_scraper import RemoteOKScraper

# Initialize scraper
scraper = RemoteOKScraper()

# Scrape jobs
jobs = scraper.scrape("Python Developer", limit=50)

# Process results
for job in jobs:
    print(f"{job['job_title']} at {job['company_name']}")
    print(f"Location: {job['location']}")
    print(f"Salary: {job['salary']}")
    print(f"URL: {job['job_url']}")
    print("---")
```

### With Parsed Query

```python
from utils.query_parser import query_parser

# Parse natural language query
parsed_query = query_parser.parse("Python Developer role remote")

# Scrape using parsed query
jobs = scraper.scrape_from_parsed_query(parsed_query, limit=50)
```

## Data Format

Each job dictionary contains:
```python
{
    'job_title': str,        # Job title from 'position' field
    'company_name': str,     # Company name
    'location': str,         # Location (usually 'Remote')
    'job_url': str,          # URL to job posting
    'salary': str,           # Salary or 'Not specified'
    'description': str,      # Description with tags appended
    'posted_date': str,      # Converted epoch timestamp (YYYY-MM-DD)
    'source': 'RemoteOK'     # Always 'RemoteOK'
}
```

## Dependencies

- `requests`: HTTP library
- `models.job_model`: Data validation
- `utils.query_parser`: Natural language query support
- `utils.logger`: Logging
- `config`: Configuration management

## Advantages of API Approach

1. **Reliability**: Official API is more stable than web scraping
2. **Performance**: Single API call vs multiple page loads
3. **Structure**: Consistent data format
4. **No Parsing**: No HTML parsing required
5. **Real-time**: Always returns current job listings

## Limitations

1. **No Pagination**: API returns all jobs at once
2. **Limited Filtering**: Must filter client-side
3. **Rate Limits**: No official rate limit documentation
4. **API Changes**: API structure may change without notice

## Maintenance

### Updating for API Changes
If RemoteOK API structure changes:

1. Check API response format
2. Update field mappings in `_extract_job_data()`
3. Adjust metadata filtering logic
4. Test with sample API calls
5. Update unit tests accordingly

### Common Issues

**Issue**: API returns empty array
- **Solution**: Check API status, verify endpoint URL

**Issue**: Jobs not matching search query
- **Solution**: Check search term matching logic, verify case sensitivity

**Issue**: Epoch timestamp conversion fails
- **Solution**: Add error handling for invalid timestamps

**Issue**: Rate limiting/blocking
- **Solution**: Add delays between requests, implement caching

## Future Enhancements

1. **Caching**: Cache API responses to reduce calls
2. **Advanced Filtering**: Add filters for salary, experience level
3. **Webhook Support**: Listen for new job notifications
4. **Incremental Updates**: Track last fetch time for delta updates
5. **Search API**: Use RemoteOK's search API if available

## References

- RemoteOK API: https://remoteok.com/api
- RemoteOK Documentation: https://remoteok.com/about
- Requests Documentation: https://requests.readthedocs.io/
