# Environment Setup Guide

This guide covers the complete setup process for the Job Agent project, including virtual environment creation, dependency installation, and configuration.

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git (for version control)
- Firecrawl API key (for Wellfound scraping)

## Step 1: Clone the Repository

```bash
git clone <repository-url>
cd job-agent
```

## Step 2: Create Virtual Environment

### Windows (PowerShell)
```powershell
python -m venv venv
.\venv\Scripts\activate
```

### Windows (Command Prompt)
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

### Linux/macOS
```bash
python3 -m venv venv
source venv/bin/activate
```

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `requests==2.31.0` - HTTP library for web requests
- `beautifulsoup4==4.12.2` - HTML parsing library
- `pandas==2.0.3` - Data manipulation and CSV handling
- `lxml==4.9.3` - XML/HTML parser
- `firecrawl-py` - Firecrawl API client for Wellfound scraping

## Step 4: Configure Environment Variables

### Option 1: Using .env file (Recommended)

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit the `.env` file with your actual configuration:
```env
# Firecrawl API Key (required for Wellfound scraping)
FIRECRAWL_API_KEY=your_actual_firecrawl_api_key_here

# Scraping Configuration
DEFAULT_LIMIT=50
REQUEST_TIMEOUT=10
RETRY_ATTEMPTS=3
RETRY_DELAY=2

# Rate Limiting (delay between requests in seconds)
RATE_LIMIT_DELAY=1.0

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=job_agent.log

# Storage Configuration
DEFAULT_OUTPUT_FILE=jobs.csv
```

### Option 2: Setting Environment Variables Directly

#### Windows (PowerShell)
```powershell
$env:FIRECRAWL_API_KEY="your_firecrawl_api_key"
$env:DEFAULT_LIMIT="50"
$env:LOG_LEVEL="INFO"
```

#### Windows (Command Prompt)
```cmd
set FIRECRAWL_API_KEY=your_firecrawl_api_key
set DEFAULT_LIMIT=50
set LOG_LEVEL=INFO
```

#### Linux/macOS
```bash
export FIRECRAWL_API_KEY="your_firecrawl_api_key"
export DEFAULT_LIMIT=50
export LOG_LEVEL="INFO"
```

### Getting a Firecrawl API Key

1. Visit [Firecrawl](https://www.firecrawl.dev/)
2. Sign up for an account
3. Navigate to the API section
4. Generate an API key
5. Add it to your environment variables

## Step 5: Verify Installation

Run the following command to verify everything is set up correctly:

```bash
python -c "import requests; import bs4; import pandas; import firecrawl; print('All dependencies installed successfully!')"
```

## Step 6: Test the Configuration

Create a test script to verify your configuration:

```python
# test_config.py
from config import config
from utils.logger import get_logger

def test_configuration():
    print("Testing configuration...")
    print(f"Firecrawl API Key: {'Set' if config.firecrawl_api_key else 'Not Set'}")
    print(f"Default Limit: {config.default_limit}")
    print(f"Request Timeout: {config.request_timeout}")
    print(f"Retry Attempts: {config.retry_attempts}")
    print(f"Rate Limit Delay: {config.rate_limit_delay}")
    print(f"Log Level: {config.log_level}")
    
    logger = get_logger()
    logger.info("Configuration test successful")
    
    if config.validate():
        print("✓ Configuration is valid")
    else:
        print("✗ Configuration has issues")

if __name__ == "__main__":
    test_configuration()
```

Run the test:
```bash
python test_config.py
```

## Step 7: Project Structure Verification

Ensure your project structure matches the expected layout:

```
job-agent/
├── config.py                 # Configuration management
├── main.py                   # Main entry point
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (create from .env.example)
├── .env.example             # Environment variables template
├── scrapers/                 # Job board scrapers
│   ├── __init__.py
│   ├── base_scraper.py      # Base scraper class
│   ├── naukri_scraper.py    # Naukri.com scraper
│   ├── remoteok_scraper.py  # RemoteOK scraper
│   └── wellfound_scraper.py # Wellfound scraper
├── storage/                  # Data storage
│   ├── __init__.py
│   └── csv_storage.py       # CSV storage handler
├── models/                   # Data models
│   ├── __init__.py
│   └── job_model.py         # Job data model and validation
├── utils/                    # Utility functions
│   ├── __init__.py
│   └── logger.py            # Logging infrastructure
└── docs/                     # Documentation
    ├── context.md           # Project context
    ├── architecture.md      # Phase-wise architecture
    └── setup.md             # This file
```

## Troubleshooting

### Issue: ModuleNotFoundError
**Solution**: Ensure you've activated your virtual environment and installed dependencies:
```bash
# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
.\venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Issue: FIRECRAWL_API_KEY not found
**Solution**: Ensure you've set the environment variable or created the `.env` file:
```bash
# Check if variable is set
echo $FIRECRAWL_API_KEY  # Linux/macOS
echo %FIRECRAWL_API_KEY%  # Windows

# Or check .env file exists
ls .env  # Linux/macOS
dir .env  # Windows
```

### Issue: Permission denied when creating virtual environment
**Solution**: Run the command with appropriate permissions or use a user-level virtual environment:
```bash
python -m venv --user venv
```

### Issue: pip install fails
**Solution**: Upgrade pip and try again:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Development Setup

For development, you may want to install additional tools:

```bash
# Install development dependencies (optional)
pip install pytest pytest-cov black flake8

# Install pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

## Next Steps

After completing the setup:

1. Review the [architecture.md](architecture.md) to understand the implementation phases
2. Check the [context.md](context.md) for project details
3. Read the [README.md](../README.md) for usage instructions
4. Start implementing Phase 2 of the architecture

## Security Notes

- Never commit `.env` file to version control
- Keep your Firecrawl API key secure
- Use different API keys for development and production
- Rotate API keys regularly
- Don't share API keys in public repositories

## Support

If you encounter issues not covered in this guide:
1. Check the [README.md](../README.md) troubleshooting section
2. Review the [architecture.md](architecture.md) for implementation details
3. Check the logs in `job_agent.log` (if logging is enabled)
