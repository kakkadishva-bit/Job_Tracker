# Wellfound Scraper Implementation Documentation

## Overview
The Wellfound scraper uses Firecrawl API to fetch job listings from Wellfound (formerly AngelList). It implements robust error handling, retry logic, and intelligent markdown parsing to extract job data from dynamic JavaScript-rendered content.

## Architecture

### Class Structure
```python
class WellfoundScraper(BaseScraper):
    """Enhanced scraper for Wellfound job board using Firecrawl"""
```

The scraper extends the `BaseScraper` class, inheriting common functionality like:
- Retry logic with configurable attempts
- Rate limiting
- Logging integration
- Data validation
- Session management

### Key Components

#### 1. Firecrawl Integration
- **Method**: `_scrape_with_firecrawl(url: str, job_title: str, limit: int) -> list`
- **Purpose**: Fetches Wellfound page content using Firecrawl API
- **API**: Firecrawl API (requires FIRECRAWL_API_KEY)
- **Features**:
  - Automatic retry logic on failures
  - Markdown format extraction
  - Main content only (no navigation/footer)
  - Configurable timeout and retry attempts

**Firecrawl Parameters**:
```python
{
    'formats': ['markdown'],
    'onlyMainContent': True
}
```

#### 2. URL Construction
- **Method**: `_build_search_url(job_title: str) -> str`
- **Purpose**: Constructs Wellfound search URLs
- **Format**: `https://wellfound.com/role/{encoded_job_title}`
- **Example**: `https://wellfound.com/role/software-engineer`

#### 3. Markdown Parsing
- **Method**: `_parse_markdown_jobs(markdown_content: str, job_title: str, limit: int) -> list`
- **Purpose**: Parses markdown content to extract job listings
- **Features**:
  - Splits content into job sections
  - Extracts structured job data
  - Handles missing fields gracefully
  - Validates and normalizes data

**Section Splitting Logic**:
```python
# Split by headings (# or ##)
# Each section represents one job
# Headers indicate new job sections
```

#### 4. Data Extraction
- **Method**: `_extract_job_from_section(section: str, job_title: str) -> Dict`
- **Purpose**: Extracts job data from a markdown section
- **Features**:
  - Identifies company, location, salary, URL lines
  - Extracts description from remaining content
  - Sets sensible defaults for missing fields
  - Normalizes extracted data

**Extraction Patterns**:
- **Company**: Lines with "company", "startup", "at", "by"
- **Location**: Lines with "location", "remote", "based in", "office"
- **Salary**: Lines with "salary", "compensation", "pay", "$", "equity", "stock"
- **URL**: Lines starting with "http" or "www."

#### 5. Helper Methods
- **`_split_into_job_sections(markdown_content) -> list`**: Splits markdown into job sections
- **`_is_company_line(line) -> bool`**: Detects company information lines
- **`_extract_company_name(line) -> str`**: Extracts company name
- **`_is_location_line(line) -> bool`**: Detects location information lines
- **`_extract_location(line) -> str`**: Extracts location
- **`_is_salary_line(line) -> bool`**: Detects salary information lines
- **`_extract_salary(line) -> str`**: Extracts salary
- **`_is_url_line(line) -> bool`**: Detects URL lines
- **`_extract_url(line) -> str`**: Extracts and normalizes URL
- **`_is_metadata_line(line) -> bool`**: Detects metadata lines

## Data Flow

```
User Request (job_title, limit)
    ↓
scrape(job_title, limit)
    ↓
_build_search_url(job_title)
    ↓
_scrape_with_firecrawl(url, job_title, limit)
    ↓
For each attempt (retry logic):
    FirecrawlApp.scrape_url(url, params)
    ↓
    Get markdown content
    ↓
    _parse_markdown_jobs(markdown, job_title, limit)
    ↓
    _split_into_job_sections(markdown)
    ↓
    For each section:
        _extract_job_from_section(section, job_title)
        ↓
        Extract metadata (company, location, salary, url)
        ↓
        Build description from remaining lines
        ↓
        create_job_object(job_data) [validation]
        ↓
        job.to_dict()
    ↓
Return list of job dictionaries
```

## Error Handling

### 1. Firecrawl API Failures
- **API Key Missing**: Logs warning, returns empty list
- **Network Errors**: Retry with exponential backoff
- **Timeout Errors**: Configurable timeout with retry
- **API Errors**: Retry logic with attempt limits
- **No Markdown Content**: Logs warning, retries

### 2. Data Validation
- Integration with Job model validation
- Invalid jobs are filtered out
- Missing required fields logged as warnings
- Graceful handling of missing optional fields

### 3. Parsing Failures
- Invalid markdown structure handled gracefully
- Missing sections don't crash scraper
- Malformed lines skipped with warnings
- Empty sections filtered out

## Configuration

The scraper uses configuration from `config.py`:

```python
# Retry logic
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2  # seconds

# Request timeout
REQUEST_TIMEOUT = 10  # seconds
```

### Environment Variables

```bash
FIRECRAWL_API_KEY=your_firecrawl_api_key_here
```

## Testing

### Unit Tests
Located in `tests/test_wellfound_scraper.py`:

1. **Test Initialization**: Verifies scraper setup
2. **Test URL Building**: Tests search URL construction
3. **Test Company Detection**: Tests company line detection
4. **Test Company Extraction**: Tests company name extraction
5. **Test Location Detection**: Tests location line detection
6. **Test Location Extraction**: Tests location extraction
7. **Test Salary Detection**: Tests salary line detection
8. **Test URL Detection**: Tests URL line detection
9. **Test URL Extraction**: Tests URL extraction
10. **Test Metadata Detection**: Tests metadata line detection
11. **Test Section Splitting**: Tests markdown section splitting
12. **Test Job Extraction**: Tests complete job data extraction
13. **Test Missing Fields**: Tests handling of incomplete data
14. **Test Basic Scraping**: Tests scraping functionality
15. **Test No Firecrawl**: Tests behavior without API key
16. **Test Firecrawl Success**: Tests successful Firecrawl call
17. **Test Firecrawl Retry**: Tests retry logic

### Running Tests
```bash
# Run all tests
python -m pytest tests/test_wellfound_scraper.py

# Run with coverage
python -m pytest tests/test_wellfound_scraper.py --cov=scrapers.wellfound_scraper

# Run specific test
python -m pytest tests/test_wellfound_scraper.py::TestWellfoundScraper::test_extract_job_from_section
```

### Integration Tests
Integration tests require Firecrawl API key and are skipped by default:
```bash
# Set API key
export FIRECRAWL_API_KEY=your_key

# Run integration tests
python -m pytest tests/test_wellfound_scraper.py::TestWellfoundScraperIntegration --no-skip
```

## Performance Characteristics

### Firecrawl Performance
- Single API call per scrape
- Handles JavaScript-rendered content
- Response time varies (2-10 seconds typical)
- Rate limited by Firecrawl API

### Parsing Performance
- Markdown parsing is fast (< 100ms)
- Section splitting is O(n) where n = lines
- Pattern matching is efficient
- Memory usage is low

### Resource Usage
- Memory: Low (processes one section at a time)
- Network: 1 Firecrawl API call per scrape
- CPU: Low (string matching is efficient)
- API Costs: Usage-based pricing from Firecrawl

## Firecrawl API Details

### Authentication
- **Method**: API Key
- **Environment Variable**: `FIRECRAWL_API_KEY`
- **Required**: Yes (scraper won't work without it)

### Scrape Parameters
- **formats**: `['markdown']` - Returns markdown format
- **onlyMainContent**: `True` - Excludes navigation/footer
- **timeout**: Configurable via config

### Response Structure
```json
{
  "markdown": "# Job Title\nCompany: ...\n\nDescription...",
  "content": "HTML content if requested",
  "metadata": {...}
}
```

### Rate Limits
- Determined by Firecrawl pricing plan
- No official rate limit documentation
- Be reasonable with request frequency

## Markdown Structure

Wellfound pages typically have this structure in markdown:

```markdown
## Software Engineer
Company: Tech Startup
Location: Remote
Salary: $100k - $150k
https://wellfound.com/l/12345

We're looking for a talented software engineer...

## Senior Developer
Company: Another Startup
Location: San Francisco
Salary: $120k - $180k
https://wellfound.com/l/67890

Senior developer role with...
```

## Usage Example

```python
from scrapers.wellfound_scraper import WellfoundScraper

# Initialize scraper (requires FIRECRAWL_API_KEY)
scraper = WellfoundScraper()

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

### With Parsed Query

```python
from utils.query_parser import query_parser

# Parse natural language query
parsed_query = query_parser.parse("Software Engineer role remote")

# Scrape using parsed query
jobs = scraper.scrape_from_parsed_query(parsed_query, limit=50)
```

## Data Format

Each job dictionary contains:
```python
{
    'job_title': str,        # Job title from heading
    'company_name': str,     # Company name
    'location': str,         # Location (default 'Remote')
    'job_url': str,          # URL to job posting
    'salary': str,           # Salary or 'Not specified'
    'description': str,      # Description from non-metadata lines
    'posted_date': str,      # Empty string (not available in markdown)
    'source': 'Wellfound'    # Always 'Wellfound'
}
```

## Dependencies

- `firecrawl-py`: Firecrawl API client
- `models.job_model`: Data validation
- `utils.query_parser`: Natural language query support
- `utils.logger`: Logging
- `config`: Configuration management

## Advantages of Firecrawl Approach

1. **JavaScript Support**: Handles dynamic content rendering
2. **No Maintenance**: Firecrawl handles website changes
3. **Clean Output**: Markdown format is easy to parse
4. **Reliable**: Professional scraping service
5. **Main Content Only**: Filters out navigation/footer

## Limitations

1. **API Cost**: Usage-based pricing can be expensive
2. **API Key Required**: Must set environment variable
3. **Rate Limits**: Limited by Firecrawl pricing plan
4. **External Dependency**: Relies on third-party service
5. **Posted Date**: Not available in markdown content

## Maintenance

### Updating for Markdown Changes
If Wellfound markdown structure changes:

1. Get sample markdown from Firecrawl
2. Analyze new structure patterns
3. Update extraction patterns in helper methods
4. Test with sample data
5. Update unit tests accordingly

### Common Issues

**Issue**: No markdown content returned
- **Solution**: Check Firecrawl API key, verify URL format

**Issue**: Jobs not extracted correctly
- **Solution**: Update extraction patterns, check markdown structure

**Issue**: Firecrawl API errors
- **Solution**: Check API key, verify account status, check rate limits

**Issue**: High API costs
- **Solution**: Implement caching, reduce scrape frequency

## Best Practices

1. **API Key Security**: Never commit API keys to version control
2. **Rate Limiting**: Be reasonable with request frequency
3. **Error Handling**: Always check for Firecrawl initialization
4. **Caching**: Consider caching results to reduce API calls
5. **Monitoring**: Track API usage and costs

## Future Enhancements

1. **Caching**: Cache Firecrawl responses to reduce costs
2. **Advanced Filtering**: Add filters for salary, location, company size
3. **Pagination**: Handle multiple pages if Wellfound implements it
4. **Posted Dates**: Try to extract posting dates if available
5. **Alternative Formats**: Try HTML format if markdown is insufficient

## Troubleshooting

### FIRECRAWL_API_KEY Not Set
```bash
export FIRECRAWL_API_KEY=your_key_here
```

### Firecrawl API Errors
- Verify API key is valid
- Check Firecrawl account status
- Ensure sufficient API credits
- Check for service outages

### Poor Extraction Results
- Get sample markdown to analyze structure
- Update extraction patterns
- Add more keyword variations
- Improve section splitting logic

## References

- Firecrawl Documentation: https://docs.firecrawl.dev/
- Firecrawl Pricing: https://www.firecrawl.dev/pricing
- Wellfound: https://wellfound.com/
- Markdown Specification: https://commonmark.org/
