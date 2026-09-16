"""Job data model and validation schemas"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SourcePlatform(Enum):
    """Enum for job source platforms"""
    NAUKRI = "Naukri"
    REMOTEOK = "RemoteOK"
    WELLFOUND = "Wellfound"


@dataclass
class Job:
    """Standard job data model"""
    
    job_title: str
    company_name: str
    location: str
    job_url: str
    salary: str = "Not specified"
    description: str = ""
    posted_date: str = ""
    source: str = ""
    
    def __post_init__(self):
        """Validate and normalize job data after initialization"""
        self.job_title = self._clean_text(self.job_title)
        self.company_name = self._clean_text(self.company_name)
        self.location = self._clean_text(self.location)
        self.job_url = self._clean_url(self.job_url)
        self.salary = self._clean_text(self.salary)
        self.description = self._clean_text(self.description)
        self.posted_date = self._clean_text(self.posted_date)
        self.source = self._clean_text(self.source)
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        return text.strip()
    
    @staticmethod
    def _clean_url(url: str) -> str:
        """Clean and validate URL"""
        if not url:
            return ""
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            return ""
        return url
    
    def to_dict(self) -> Dict[str, str]:
        """Convert job to dictionary"""
        return {
            'job_title': self.job_title,
            'company_name': self.company_name,
            'location': self.location,
            'job_url': self.job_url,
            'salary': self.salary,
            'description': self.description,
            'posted_date': self.posted_date,
            'source': self.source
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        """Create Job instance from dictionary"""
        return cls(
            job_title=data.get('job_title', ''),
            company_name=data.get('company_name', ''),
            location=data.get('location', ''),
            job_url=data.get('job_url', ''),
            salary=data.get('salary', 'Not specified'),
            description=data.get('description', ''),
            posted_date=data.get('posted_date', ''),
            source=data.get('source', '')
        )
    
    def is_valid(self) -> bool:
        """Validate job data"""
        if not self.job_title:
            return False
        if not self.company_name:
            return False
        if not self.job_url:
            return False
        if self.source not in [platform.value for platform in SourcePlatform]:
            return False
        return True
    
    def __str__(self) -> str:
        """String representation of job"""
        return f"{self.job_title} at {self.company_name} ({self.source})"


class JobValidator:
    """Validator for job data"""
    
    REQUIRED_FIELDS = ['job_title', 'company_name', 'job_url', 'source']
    VALID_SOURCES = [platform.value for platform in SourcePlatform]
    
    @classmethod
    def validate(cls, job_data: Dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate job data
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Check required fields
        for field in cls.REQUIRED_FIELDS:
            if field not in job_data or not job_data[field]:
                errors.append(f"Missing required field: {field}")
        
        # Validate source
        if 'source' in job_data and job_data['source']:
            if job_data['source'] not in cls.VALID_SOURCES:
                errors.append(f"Invalid source: {job_data['source']}")
        
        # Validate URL format
        if 'job_url' in job_data and job_data['job_url']:
            url = job_data['job_url']
            if not url.startswith(('http://', 'https://')):
                errors.append(f"Invalid URL format: {url}")
        
        return (len(errors) == 0, errors)
    
    @classmethod
    def sanitize(cls, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize job data"""
        sanitized = {}
        
        for key, value in job_data.items():
            if isinstance(value, str):
                sanitized[key] = value.strip()
            else:
                sanitized[key] = value
        
        # Set default values for missing optional fields
        if 'salary' not in sanitized or not sanitized['salary']:
            sanitized['salary'] = 'Not specified'
        if 'description' not in sanitized:
            sanitized['description'] = ''
        if 'posted_date' not in sanitized:
            sanitized['posted_date'] = ''
        
        return sanitized
