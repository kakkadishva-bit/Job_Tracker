"""Configuration management for Job Agent"""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class Config:
    """Configuration class for Job Agent"""
    
    # Firecrawl API Configuration
    firecrawl_api_key: Optional[str] = None
    
    # Scraping Configuration
    default_limit: int = 50
    request_timeout: int = 10
    retry_attempts: int = 3
    retry_delay: int = 2
    
    # Rate Limiting
    rate_limit_delay: float = 1.0
    
    # Logging Configuration
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # Storage Configuration
    default_output_file: str = "jobs.csv"
    
    def __post_init__(self):
        """Load configuration from environment variables"""
        # Load Firecrawl API key
        self.firecrawl_api_key = os.getenv('FIRECRAWL_API_KEY')
        
        # Load optional configurations
        self.default_limit = int(os.getenv('DEFAULT_LIMIT', self.default_limit))
        self.request_timeout = int(os.getenv('REQUEST_TIMEOUT', self.request_timeout))
        self.retry_attempts = int(os.getenv('RETRY_ATTEMPTS', self.retry_attempts))
        self.retry_delay = int(os.getenv('RETRY_DELAY', self.retry_delay))
        self.rate_limit_delay = float(os.getenv('RATE_LIMIT_DELAY', self.rate_limit_delay))
        self.log_level = os.getenv('LOG_LEVEL', self.log_level)
        self.log_file = os.getenv('LOG_FILE', self.log_file)
        self.default_output_file = os.getenv('DEFAULT_OUTPUT_FILE', self.default_output_file)
    
    def validate(self) -> bool:
        """Validate configuration"""
        if not self.firecrawl_api_key:
            print("Warning: FIRECRAWL_API_KEY not set. Wellfound scraping will be disabled.")
        
        return True


# Global configuration instance
config = Config()
