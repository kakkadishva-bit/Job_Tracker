"""Natural language query parser for job searches"""

import re
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from utils.logger import get_logger


@dataclass
class ParsedQuery:
    """Parsed job search query"""
    job_title: str
    location: Optional[str] = None
    keywords: list = None
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


class QueryParser:
    """Parse natural language job search queries"""
    
    # Common location indicators
    LOCATION_INDICATORS = [
        'in', 'at', 'located in', 'based in', 'position in', 
        'role in', 'job in', 'work in', 'opportunity in'
    ]
    
    # Common Indian cities (can be expanded)
    INDIAN_CITIES = [
        'bangalore', 'bengaluru', 'mumbai', 'delhi', 'pune', 'hyderabad',
        'chennai', 'kolkata', 'ahmedabad', 'jaipur', 'lucknow', 'chandigarh',
        'gurgaon', 'noida', 'bangalore', 'bengaluru'
    ]
    
    # Common job role indicators
    ROLE_INDICATORS = [
        'role', 'position', 'job', 'opportunity', 'opening', 'vacancy'
    ]
    
    def __init__(self):
        self.logger = get_logger()
    
    def parse(self, query: str) -> ParsedQuery:
        """
        Parse natural language query into job title and location
        
        Args:
            query: Natural language query (e.g., "Product Manager role in bangalore")
            
        Returns:
            ParsedQuery object with job_title and location
        """
        query = query.strip().lower()
        self.logger.debug(f"Parsing query: {query}")
        
        # Try to extract location first
        location = self._extract_location(query)
        
        # Extract job title (remove location and role indicators)
        job_title = self._extract_job_title(query, location)
        
        # Extract additional keywords
        keywords = self._extract_keywords(query, job_title, location)
        
        parsed = ParsedQuery(
            job_title=job_title,
            location=location,
            keywords=keywords
        )
        
        self.logger.info(f"Parsed query: job_title='{job_title}', location='{location}'")
        return parsed
    
    def _extract_location(self, query: str) -> Optional[str]:
        """Extract location from query"""
        # Check for location indicators
        for indicator in self.LOCATION_INDICATORS:
            pattern = rf'{indicator}\s+([a-zA-Z\s]+?)(?:\s|$|,)'
            match = re.search(pattern, query, re.IGNORECASE)
            
            if match:
                location = match.group(1).strip()
                # Check if it's a known city
                if self._is_known_location(location):
                    return location.title()
        
        # Check for known cities without indicators
        for city in self.INDIAN_CITIES:
            if city in query:
                return city.title()
        
        return None
    
    def _extract_job_title(self, query: str, location: Optional[str]) -> str:
        """Extract job title from query"""
        # Remove location if present
        if location:
            query = query.replace(location.lower(), '')
        
        # Remove role indicators
        for indicator in self.ROLE_INDICATORS:
            query = query.replace(indicator, '')
        
        # Remove common words
        stop_words = ['in', 'at', 'for', 'the', 'a', 'an', 'and', 'or', 'with']
        words = query.split()
        filtered_words = [word for word in words if word.lower() not in stop_words]
        
        job_title = ' '.join(filtered_words).strip()
        
        # Clean up extra spaces
        job_title = re.sub(r'\s+', ' ', job_title)
        
        return job_title
    
    def _extract_keywords(self, query: str, job_title: str, location: Optional[str]) -> list:
        """Extract additional keywords from query"""
        # This is a simple implementation - can be enhanced with NLP
        keywords = []
        
        # Remove job title and location from query
        remaining = query.lower()
        if job_title:
            remaining = remaining.replace(job_title.lower(), '')
        if location:
            remaining = remaining.replace(location.lower(), '')
        
        # Extract remaining meaningful words
        words = remaining.split()
        for word in words:
            if len(word) > 2 and word not in self.ROLE_INDICATORS:
                keywords.append(word)
        
        return keywords
    
    def _is_known_location(self, location: str) -> bool:
        """Check if location is a known city"""
        location_lower = location.lower()
        return any(city in location_lower or location_lower in city 
                   for city in self.INDIAN_CITIES)
    
    def build_naukri_url(self, parsed_query: ParsedQuery) -> str:
        """
        Build Naukri search URL from parsed query
        
        Args:
            parsed_query: Parsed query object
            
        Returns:
            Naukri search URL
        """
        from urllib.parse import quote
        
        base_url = "https://www.naukri.com"
        
        # Build job title part
        job_title_encoded = quote(parsed_query.job_title)
        
        # Add location if present
        if parsed_query.location:
            location_encoded = quote(parsed_query.location)
            url = f"{base_url}/{job_title_encoded}-jobs-in-{location_encoded}"
        else:
            url = f"{base_url}/{job_title_encoded}-jobs"
        
        return url
    
    def build_remoteok_query(self, parsed_query: ParsedQuery) -> str:
        """
        Build RemoteOK search query from parsed query
        
        Args:
            parsed_query: Parsed query object
            
        Returns:
            Search query string for RemoteOK API
        """
        # RemoteOK API searches by job title/keywords
        query = parsed_query.job_title
        
        # Add location as keyword if present
        if parsed_query.location:
            query = f"{query} {parsed_query.location}"
        
        return query
    
    def build_wellfound_url(self, parsed_query: ParsedQuery) -> str:
        """
        Build Wellfound search URL from parsed query
        
        Args:
            parsed_query: Parsed query object
            
        Returns:
            Wellfound search URL
        """
        from urllib.parse import quote
        
        base_url = "https://wellfound.com/role"
        job_title_encoded = quote(parsed_query.job_title)
        
        return f"{base_url}/{job_title_encoded}"


# Global query parser instance
query_parser = QueryParser()
