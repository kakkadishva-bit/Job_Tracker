# Job Agent Project Context

## Problem Statement
Job seekers often need to manually search across multiple job boards (Naukri, RemoteOK, Wellfound) to find relevant opportunities. This process is time-consuming, repetitive, and inefficient as it requires:
- Visiting multiple websites
- Searching for the same job title across different platforms
- Manually collecting and organizing job details
- Dealing with different interfaces and data formats

## Solution
Build an automated job agent that:
1. Scrapes job listings from multiple sources (Naukri, RemoteOK, Wellfound)
2. Accepts job role and location as separate inputs from the user
3. Constructs accurate search URLs for each platform based on job role and location
4. Normalizes and consolidates job data from different sources
5. Stores all results in a structured CSV file for easy analysis
6. Supports HTML page caching for offline scraping and debugging

## Key Features
- Multi-platform job scraping (Naukri, RemoteOK, Wellfound)
- Separate job role and location inputs for precise searches
- Intelligent URL construction for each platform
- HTML page caching for offline scraping and debugging
- Search by job role with optional location filters
- Data normalization across different job board formats
- CSV export for easy data analysis and filtering
- Configurable search parameters

## Tech Stack
- Python for scraping and data processing
- BeautifulSoup/requests for HTML web scraping (Naukri)
- Public API integration (RemoteOK)
- Firecrawl for advanced web scraping (Wellfound)
- pandas for CSV handling
- CSV for data storage
- HTML caching system for offline scraping
- Natural language query parser

## Scraping Approach by Platform
- **Naukri**: HTML scraping using BeautifulSoup and requests to parse job listings from the website
- **RemoteOK**: Public API integration to fetch job data directly from their API endpoint
- **Wellfound**: Firecrawl for robust web scraping to handle dynamic content and JavaScript-rendered pages

## Data Fields to Capture
- Job Title
- Company Name
- Location
- Job URL
- Salary/Compensation
- Job Description
- Posting Date
- Source Platform (Naukri/RemoteOK/Wellfound)

## Implementation Phases

### Phase 1: Project Setup and Infrastructure
- Set up project structure and directories
- Implement configuration management with environment variables
- Create logging infrastructure
- Define data models and validation
- Enhance base scraper with common functionality
- Create environment setup documentation

### Phase 2: Naukri Scraper Implementation
- Research Naukri.com HTML structure and patterns
- Implement Naukri scraper with HTML parsing using BeautifulSoup
- Add pagination handling for multiple pages
- Implement data extraction and normalization
- Add error handling and retry logic
- Create unit tests for Naukri scraper
- Document Naukri scraper implementation

### Phase 3: RemoteOK API Integration
- Research RemoteOK public API documentation
- Implement RemoteOK scraper with API integration
- Add error handling and rate limiting for API calls
- Implement data filtering and processing
- Create unit tests for RemoteOK scraper
- Document RemoteOK API integration

### Phase 4: Wellfound Firecrawl Integration
- Set up Firecrawl API integration
- Implement Wellfound scraper using Firecrawl
- Improve markdown parsing for job data extraction
- Add error handling for Firecrawl API
- Create unit tests for Wellfound scraper
- Document Wellfound Firecrawl integration

### Phase 5: Multi-Platform Integration
- Implement main entry point that accepts job role and location as separate inputs
- Trigger all three scrapers (Naukri, RemoteOK, Wellfound) with job role and location
- Consolidate and normalize job data from all platforms
- Store aggregated results in CSV file
- Add command-line interface with options for output file and job limits
- Implement HTML caching support for offline scraping
- Create integration tests for end-to-end workflow
- Document usage and deployment instructions
