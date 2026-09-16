"""
Configuration for Precious Metals & ETF Investment Intelligence Platform
"""
import os

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'precious-metals-platform-secret-key-2026')
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'platform.db')
    CACHE_TIMEOUT = 300  # 5 minutes
    API_RATE_LIMIT = 60  # requests per minute
    
    # Data Sources
    DATA_SOURCES = {
        'nse': {
            'name': 'NSE India',
            'url': 'https://www.nseindia.com',
            'api_url': 'https://www.nseindia.com/api',
            'reliability': 0.95,
        },
        'bse': {
            'name': 'BSE India',
            'url': 'https://www.bseindia.com',
            'api_url': 'https://www.bseindia.com/api',
            'reliability': 0.95,
        },
        'amfi': {
            'name': 'AMFI India',
            'url': 'https://www.amfiindia.com',
            'reliability': 0.90,
        },
        'angel_one': {
            'name': 'Angel One',
            'url': 'https://www.angelone.in',
            'reliability': 0.85,
        },
        'edelweiss': {
            'name': 'Edelweiss Mutual Fund',
            'url': 'https://www.edelweissmf.com',
            'reliability': 0.85,
        },
    }
    
    # Disclaimer
    DISCLAIMER = (
        "This platform provides educational and informational content only "
        "and does not constitute financial advice. Investment decisions should "
        "be made after consulting a qualified financial advisor."
    )


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
}