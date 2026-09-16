"""HTML page caching and saving functionality"""

import os
import hashlib
import json
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
from utils.logger import get_logger
from config import config


class HTMLCache:
    """Cache HTML pages for offline scraping and debugging"""
    
    def __init__(self, cache_dir: str = "html_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.logger = get_logger()
        self.cache_duration = timedelta(hours=24)  # Cache for 24 hours
    
    def _get_cache_key(self, url: str) -> str:
        """Generate cache key from URL"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def _get_cache_path(self, url: str) -> Path:
        """Get cache file path for URL"""
        cache_key = self._get_cache_key(url)
        return self.cache_dir / f"{cache_key}.html"
    
    def _get_metadata_path(self, url: str) -> Path:
        """Get metadata file path for URL"""
        cache_key = self._get_cache_key(url)
        return self.cache_dir / f"{cache_key}.json"
    
    def is_cached(self, url: str) -> bool:
        """Check if URL is cached and not expired"""
        cache_path = self._get_cache_path(url)
        metadata_path = self._get_metadata_path(url)
        
        if not cache_path.exists() or not metadata_path.exists():
            return False
        
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            cached_time = datetime.fromisoformat(metadata['cached_at'])
            return datetime.now() - cached_time < self.cache_duration
            
        except Exception as e:
            self.logger.warning(f"Error checking cache metadata: {e}")
            return False
    
    def get(self, url: str) -> Optional[str]:
        """
        Get cached HTML content
        
        Args:
            url: URL to retrieve from cache
            
        Returns:
            HTML content or None if not cached/expired
        """
        if not self.is_cached(url):
            return None
        
        cache_path = self._get_cache_path(url)
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.logger.debug(f"Retrieved cached content for {url}")
            return content
            
        except Exception as e:
            self.logger.error(f"Error reading cache: {e}")
            return None
    
    def save(self, url: str, content: str):
        """
        Save HTML content to cache
        
        Args:
            url: URL being cached
            content: HTML content to save
        """
        cache_path = self._get_cache_path(url)
        metadata_path = self._get_metadata_path(url)
        
        try:
            # Save HTML content
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Save metadata
            metadata = {
                'url': url,
                'cached_at': datetime.now().isoformat(),
                'content_length': len(content)
            }
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            self.logger.debug(f"Cached content for {url}")
            
        except Exception as e:
            self.logger.error(f"Error saving to cache: {e}")
    
    def clear(self):
        """Clear all cached files"""
        try:
            for file in self.cache_dir.iterdir():
                file.unlink()
            self.logger.info("Cache cleared")
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
    
    def clear_expired(self):
        """Clear expired cache entries"""
        try:
            now = datetime.now()
            cleared = 0
            
            for metadata_file in self.cache_dir.glob("*.json"):
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    cached_time = datetime.fromisoformat(metadata['cached_at'])
                    
                    if now - cached_time >= self.cache_duration:
                        # Remove HTML file
                        html_file = metadata_file.with_suffix('.html')
                        if html_file.exists():
                            html_file.unlink()
                        
                        # Remove metadata file
                        metadata_file.unlink()
                        cleared += 1
                        
                except Exception as e:
                    self.logger.warning(f"Error processing cache entry: {e}")
            
            self.logger.info(f"Cleared {cleared} expired cache entries")
            
        except Exception as e:
            self.logger.error(f"Error clearing expired cache: {e}")


class HTMLSaver:
    """Save HTML pages for offline analysis and debugging"""
    
    def __init__(self, output_dir: str = "saved_html"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.logger = get_logger()
    
    def save_page(self, url: str, content: str, filename: Optional[str] = None):
        """
        Save HTML page to file
        
        Args:
            url: URL of the page
            content: HTML content
            filename: Optional custom filename
        """
        if not filename:
            # Generate filename from URL
            safe_url = url.replace('://', '_').replace('/', '_').replace('?', '_')
            filename = f"{safe_url}.html"
        
        filepath = self.output_dir / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.info(f"Saved HTML to {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error saving HTML: {e}")
    
    def save_with_metadata(self, url: str, content: str, metadata: dict):
        """
        Save HTML page with metadata
        
        Args:
            url: URL of the page
            content: HTML content
            metadata: Additional metadata to save
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"page_{timestamp}.html"
        metadata_filename = f"page_{timestamp}.json"
        
        # Save HTML
        self.save_page(url, content, filename)
        
        # Save metadata
        metadata_path = self.output_dir / metadata_filename
        metadata['url'] = url
        metadata['saved_at'] = datetime.now().isoformat()
        metadata['html_file'] = filename
        
        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            self.logger.info(f"Saved metadata to {metadata_path}")
            
        except Exception as e:
            self.logger.error(f"Error saving metadata: {e}")
