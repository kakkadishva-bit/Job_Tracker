"""Logging infrastructure for Job Agent"""

import logging
import sys
from pathlib import Path
from typing import Optional
from config import config


class Logger:
    """Centralized logger for Job Agent"""
    
    _instance = None
    _logger = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._logger is None:
            self._setup_logger()
    
    def _setup_logger(self):
        """Setup logger with configuration"""
        self._logger = logging.getLogger('JobAgent')
        self._logger.setLevel(getattr(logging, config.log_level.upper()))
        
        # Remove existing handlers
        self._logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.log_level.upper()))
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)
        
        # File handler (if configured)
        if config.log_file:
            log_path = Path(config.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(config.log_file)
            file_handler.setLevel(getattr(logging, config.log_level.upper()))
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)
    
    def get_logger(self) -> logging.Logger:
        """Get the logger instance"""
        return self._logger
    
    def debug(self, message: str):
        """Log debug message"""
        self._logger.debug(message)
    
    def info(self, message: str):
        """Log info message"""
        self._logger.info(message)
    
    def warning(self, message: str):
        """Log warning message"""
        self._logger.warning(message)
    
    def error(self, message: str):
        """Log error message"""
        self._logger.error(message)
    
    def critical(self, message: str):
        """Log critical message"""
        self._logger.critical(message)


# Global logger instance
logger = Logger()


def get_logger() -> logging.Logger:
    """Get the global logger instance"""
    return logger.get_logger()
