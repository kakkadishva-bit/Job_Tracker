"""
Database models and initialization for Precious Metals & ETF Platform
"""
import sqlite3
import os
import json
from datetime import datetime, timedelta
import random
import math

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'platform.db')


def get_db():
    """Get database connection"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Initialize database schema"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Assets table (ETFs and Stocks)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('gold_etf', 'silver_etf', 'commodity_etf', 'mining_stock', 'special_stock')),
            exchange TEXT DEFAULT 'NSE',
            amc TEXT,
            sector TEXT,
            expense_ratio REAL,
            aum REAL,
            nav REAL,
            current_price REAL,
            daily_change_pct REAL,
            daily_change_abs REAL,
            week_52_high REAL,
            week_52_low REAL,
            volume INTEGER,
            market_cap REAL,
            isin TEXT,
            category TEXT,
            risk_score REAL,
            volatility REAL,
            beta REAL,
            sharpe_ratio REAL,
            max_drawdown REAL,
            standard_deviation REAL,
            min_investment REAL,
            sip_eligible BOOLEAN DEFAULT 1,
            recommended_horizon TEXT,
            liquidity_score REAL,
            tax_implications TEXT,
            is_active BOOLEAN DEFAULT 1,
            admin_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Historical price data
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    ''')
    
    # Portfolios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Portfolio holdings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            asset_id INTEGER NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            avg_buy_price REAL NOT NULL DEFAULT 0,
            investment_type TEXT DEFAULT 'lumpsum',
            sip_amount REAL,
            sip_frequency TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(id),
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    ''')
    
    # Watchlists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watchlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT 'Default',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Watchlist items
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watchlist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            watchlist_id INTEGER NOT NULL,
            asset_id INTEGER NOT NULL,
            notes TEXT,
            tags TEXT,
            alert_price_high REAL,
            alert_price_low REAL,
            alert_volume_spike BOOLEAN DEFAULT 0,
            alert_risk_change BOOLEAN DEFAULT 0,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (watchlist_id) REFERENCES watchlists(id),
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    ''')
    
    # News
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            summary TEXT,
            source TEXT NOT NULL,
            source_url TEXT,
            category TEXT,
            related_assets TEXT,
            sentiment TEXT,
            published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # AI Insights
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER,
            insight_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            confidence REAL,
            indicators TEXT,
            methodology TEXT,
            limitations TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    ''')
    
    # Price alerts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            alert_type TEXT NOT NULL,
            threshold_value REAL,
            is_active BOOLEAN DEFAULT 1,
            triggered_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    ''')
    
    # Audit log
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity TEXT NOT NULL,
            entity_id INTEGER,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()


def seed_data():
    """Seed database with sample assets and historical data"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM assets")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return
    
    # Sample assets data - Gold ETFs
    gold_etfs = [
        {
            'symbol': 'GOLDBEES',
            'name': 'Nippon India ETF Gold BeES',
            'type': 'gold_etf',
            'exchange': 'NSE',
            'amc': 'Nippon India Mutual Fund',
            'sector': 'Gold',
            'expense_ratio': 0.52,
            'aum': 28500.0,
            'nav': 62.45,
            'current_price': 62.52,
            'daily_change_pct': 0.82,
            'daily_change_abs': 0.51,
            'week_52_high': 68.90,
            'week_52_low': 50.20,
            'volume': 12500000,
            'market_cap': None,
            'isin': 'INF204KB15I5',
            'category': 'Gold ETF',
            'risk_score': 4.5,
            'volatility': 14.2,
            'beta': 0.85,
            'sharpe_ratio': 1.12,
            'max_drawdown': -18.5,
            'standard_deviation': 12.8,
            'min_investment': 100.0,
            'sip_eligible': True,
            'recommended_horizon': '3-5 years',
            'liquidity_score': 9.2,
            'tax_implications': 'LTCG tax at 12.5% after 1 year',
        },
        {
            'symbol': 'GOLDETF',
            'name': 'SPDR Gold Shares ETF',
            'type': 'gold_etf',
            'exchange': 'NSE',
            'amc': 'SPDR',
            'sector': 'Gold',
            'expense_ratio': 0.40,
            'aum': 57000.0,
            'nav': 58.30,
            'current_price': 58.35,
            'daily_change_pct': 0.65,
            'daily_change_abs': 0.38,
            'week_52_high': 64.20,
            'week_52_low': 47.80,
            'volume': 8900000,
            'market_cap': None,
            'isin': 'US78463V1070',
            'category': 'Gold ETF',
            'risk_score': 4.2,
            'volatility': 13.5,
            'beta': 0.82,
            'sharpe_ratio': 1.18,
            'max_drawdown': -16.2,
            'standard_deviation': 11.9,
            'min_investment': 500.0,
            'sip_eligible': True,
            'recommended_horizon': '3-5 years',
            'liquidity_score': 9.8,
            'tax_implications': 'LTCG tax at 12.5% after 1 year',
        },
        {
            'symbol': 'ICICIGOLD',
            'name': 'ICICI Prudential Gold ETF',
            'type': 'gold_etf',
            'exchange': 'NSE',
            'amc': 'ICICI Prudential Mutual Fund',
            'sector': 'Gold',
            'expense_ratio': 0.50,
            'aum': 12800.0,
            'nav': 55.80,
            'current_price': 55.92,
            'daily_change_pct': 0.75,
            'daily_change_abs': 0.42,
            'week_52_high': 61.50,
            'week_52_low': 45.30,
            'volume': 5600000,
            'market_cap': None,
            'isin': 'INF109K01YP8',
            'category': 'Gold ETF',
            'risk_score': 4.3,
            'volatility': 13.8,
            'beta': 0.84,
            'sharpe_ratio': 1.15,
            'max_drawdown': -17.0,
            'standard_deviation': 12.2,
            'min_investment': 100.0,
            'sip_eligible': True,
            'recommended_horizon': '3-5 years',
            'liquidity_score': 8.5,
            'tax_implications': 'LTCG tax at 12.5% after 1 year',
        },
        {
            'symbol': 'HDFCGOLD',
            'name': 'HDFC Gold ETF',
            'type': 'gold_etf',
            'exchange': 'NSE',
            'amc': 'HDFC Mutual Fund',
            'sector': 'Gold',
            'expense_ratio': 0.48,
            'aum': 15200.0,
            'nav': 57.20,
            'current_price': 57.28,
            'daily_change_pct': 0.70,
            'daily_change_abs': 0.40,
            'week_52_high': 63.00,
            'week_52_low': 46.50,
            'volume': 6800000,
            'market_cap': None,
            'isin': 'INF179K01VJ8',
            'category': 'Gold ETF',
            'risk_score': 4.4,
            'volatility': 14.0,
            'beta': 0.83,
            'sharpe_ratio': 1.14,
            'max_drawdown': -17.5,
            'standard_deviation': 12.5,
            'min_investment': 100.0,
            'sip_eligible': True,
            'recommended_horizon': '3-5 years',
            'liquidity_score': 8.8,
            'tax_implications': 'LTCG tax at 12.5% after 1 year',
        },
    ]
    
    # Silver ETFs
    silver_etfs = [
        {
            'symbol': 'SILVERBEES',
            'name': 'Nippon India ETF Silver BeES',
            'type': 'silver_etf',
            'exchange': 'NSE',
            'amc': 'Nippon India Mutual Fund',
            'sector': 'Silver',
            'expense_ratio': 0.55,
            'aum': 5800.0,
            'nav': 82.45,
            'current_price': 82.55,
            'daily_change_pct': 1.25,
            'daily_change_abs': 1.02,
            'week_52_high': 95.80,
            'week_52_low': 62.30,
            'volume': 3200000,
            'market_cap': None,
            'isin': 'INF204KB16I3',
            'category': 'Silver ETF',
            'risk_score': 5.8,
            'volatility': 22.5,
            'beta': 1.15,
            'sharpe_ratio': 0.95,
            'max_drawdown': -28.0,
            'standard_deviation': 20.1,
            'min_investment': 100.0,
            'sip_eligible': True,
            'recommended_horizon': '3-5 years',
            'liquidity_score': 7.5,
            'tax_implications': 'LTCG tax at 12.5% after 1 year',
        },
        {
            'symbol': 'SILVERETF',
            'name': 'iShares Silver Trust',
            'type': 'silver_etf',
            'exchange': 'NSE',
            'amc': 'iShares',
            'sector': 'Silver',
            'expense_ratio': 0.50,
            'aum': 11200.0,
            'nav': 76.30,
            'current_price': 76.40,
            'daily_change_pct': 1.10,
            'daily_change_abs': 0.83,
            'week_52_high': 89.50,
            'week_52_low': 58.20,
            'volume': 4500000,
            'market_cap': None,
            'isin': 'US464285414',
            'category': 'Silver ETF',
            'risk_score': 5.5,
            'volatility': 21.8,
            'beta': 1.12,
            'sharpe_ratio': 1.00,
            'max_drawdown': -26.5,
            'standard_deviation': 19.5,
            'min_investment': 500.0,
            'sip_eligible': True,
            'recommended_horizon': '3-5 years',
            'liquidity_score': 9.0,
            'tax_implications': 'LTCG tax at 12.5% after 1 year',
        },
        {
            'symbol': 'ABSLVSIL',
            'name': 'Aditya Birla SL Silver ETF',
            'type': 'silver_etf',
            'exchange': 'NSE',
            'amc': 'Aditya Birla SL Mutual Fund',
            'sector': 'Silver',
            'expense_ratio': 0.58,
            'aum': 3200.0,
            'nav': 78.90,
            'current_price': 79.00,
            'daily_change_pct': 1.30,
            'daily_change_abs': 1.01,
            'week_52_high': 92.40,
            'week_52_low': 60.10,
            'volume': 1800000,
            'market_cap': None,
            'isin': 'INF760K01VG8',
            'category': 'Silver ETF',
            'risk_score': 5.9,
            'volatility': 23.0,
            'beta': 1.18,
            'sharpe_ratio': 0.92,
            'max_drawdown': -29.0,
            'standard_deviation': 20.8,
            'min_investment': 100.0,
            'sip_eligible': True,
            'recommended_horizon': '3-5 years',
            'liquidity_score': 6.8,
            'tax_implications': 'LTCG tax at 12.5% after 1 year',
        },
    ]
    
    # Commodity ETFs
    commodity_etfs = [
        {
            'symbol': 'CRUDEOIL',
            'name': 'MCX Crude Oil ETF',
            'type': 'commodity_etf',
            'exchange': 'NSE',
            'amc': 'MCX',
            'sector': 'Commodities',
            'expense_ratio': 0.60,
            'aum': 2100.0,
            'nav': 45.60,
            'current_price': 45.72,
            'daily_change_pct': -0.85,
            'daily_change_abs': -0.39,
            'week_52_high': 58.90,
            'week_52_low': 32.40,
            'volume': 2100000,
            'market_cap': None,
            'isin': 'INF732E01017',
            'category': 'Commodity ETF',
            'risk_score': 7.5,
            'volatility': 32.0,
            'beta': 1.45,
            'sharpe_ratio': 0.65,
            'max_drawdown': -38.0,
            'standard_deviation': 28.5,
            'min_investment': 500.0,
            'sip_eligible': False,
            'recommended_horizon': '1-3 years',
            'liquidity_score': 6.5,
            'tax_implications': 'LTCG tax at 12.5% after 1 year',
        },
        {
            'symbol': 'COPPERETF',
            'name': 'Nippon India Copper ETF',
            'type': 'commodity_etf',
            'exchange': 'NSE',
            'amc': 'Nippon India Mutual Fund',
            'sector': 'Commodities',
            'expense_ratio': 0.65,
            'aum': 1500.0,
            'nav': 38.20,
            'current_price': 38.35,
            'daily_change_pct': 0.45,
            'daily_change_abs': 0.17,
            'week_52_high': 46.80,
            'week_52_low': 28.90,
            'volume': 900000,
            'market_cap': None,
            'isin': 'INF204KB17I1',
            'category': 'Commodity ETF',
            'risk_score': 6.8,
            'volatility': 26.5,
            'beta': 1.25,
            'sharpe_ratio': 0.78,
            'max_drawdown': -32.0,
            'standard_deviation': 23.2,
            'min_investment': 500.0,
            'sip_eligible': False,
            'recommended_horizon': '1-3 years',
            'liquidity_score': 5.8,
            'tax_implications': 'LTCG tax at 12.5% after 1 year',
        },
    ]
    
    # Mining & Precious Metal Stocks
    mining_stocks = [
        {
            'symbol': 'TATASTEEL',
            'name': 'Tata Steel Ltd',
            'type': 'mining_stock',
            'exchange': 'NSE',
            'amc': None,
            'sector': 'Mining & Metals',
            'expense_ratio': None,
            'aum': None,
            'nav': None,
            'current_price': 165.45,
            'daily_change_pct': -1.20,
            'daily_change_abs': -2.01,
            'week_52_high': 184.60,
            'week_52_low': 116.10,
            'volume': 28500000,
            'market_cap': 202800.0,
            'isin': 'INE081A01020',
            'category': 'Mining Stock',
            'risk_score': 6.2,
            'volatility': 28.5,
            'beta': 1.35,
            'sharpe_ratio': 0.72,
            'max_drawdown': -35.0,
            'standard_deviation': 25.8,
            'min_investment': 165.45,
            'sip_eligible': True,
            'recommended_horizon': '5+ years',
            'liquidity_score': 9.5,
            'tax_implications': 'LTCG tax at 12.5% above ₹1.25L; STCG at 20%',
        },
        {
            'symbol': 'HINDALCO',
            'name': 'Hindalco Industries Ltd',
            'type': 'mining_stock',
            'exchange': 'NSE',
            'amc': None,
            'sector': 'Mining & Metals',
            'expense_ratio': None,
            'aum': None,
            'nav': None,
            'current_price': 542.30,
            'daily_change_pct': 0.85,
            'daily_change_abs': 4.57,
            'week_52_high': 632.50,
            'week_52_low': 398.20,
            'volume': 15200000,
            'market_cap': 122500.0,
            'isin': 'INE019A01038',
            'category': 'Mining Stock',
            'risk_score': 6.0,
            'volatility': 26.0,
            'beta': 1.28,
            'sharpe_ratio': 0.82,
            'max_drawdown': -30.5,
            'standard_deviation': 23.5,
            'min_investment': 542.30,
            'sip_eligible': True,
            'recommended_horizon': '5+ years',
            'liquidity_score': 9.0,
            'tax_implications': 'LTCG tax at 12.5% above ₹1.25L; STCG at 20%',
        },
        {
            'symbol': 'NMDC',
            'name': 'NMDC Ltd',
            'type': 'mining_stock',
            'exchange': 'NSE',
            'amc': None,
            'sector': 'Mining & Metals',
            'expense_ratio': None,
            'aum': None,
            'nav': None,
            'current_price': 238.75,
            'daily_change_pct': -0.45,
            'daily_change_abs': -1.08,
            'week_52_high': 286.40,
            'week_52_low': 175.80,
            'volume': 12800000,
            'market_cap': 69800.0,
            'isin': 'INE584B01023',
            'category': 'Mining Stock',
            'risk_score': 5.8,
            'volatility': 24.5,
            'beta': 1.18,
            'sharpe_ratio': 0.88,
            'max_drawdown': -28.0,
            'standard_deviation': 22.0,
            'min_investment': 238.75,
            'sip_eligible': True,
            'recommended_horizon': '3-5 years',
            'liquidity_score': 8.5,
            'tax_implications': 'LTCG tax at 12.5% above ₹1.25L; STCG at 20%',
        },
        {
            'symbol': 'VEDL',
            'name': 'Vedanta Ltd',
            'type': 'mining_stock',
            'exchange': 'NSE',
            'amc': None,
            'sector': 'Mining & Metals',
            'expense_ratio': None,
            'aum': None,
            'nav': None,
            'current_price': 478.20,
            'daily_change_pct': 1.50,
            'daily_change_abs': 7.07,
            'week_52_high': 512.30,
            'week_52_low': 285.40,
            'volume': 18500000,
            'market_cap': 177200.0,
            'isin': 'INE205A01025',
            'category': 'Mining Stock',
            'risk_score': 6.8,
            'volatility': 30.5,
            'beta': 1.42,
            'sharpe_ratio': 0.68,
            'max_drawdown': -38.5,
            'standard_deviation': 27.8,
            'min_investment': 478.20,
            'sip_eligible': True,
            'recommended_horizon': '3-5 years',
            'liquidity_score': 8.2,
            'tax_implications': 'LTCG tax at 12.5% above ₹1.25L; STCG at 20%',
        },
        {
            'symbol': 'HINDZINC',
            'name': 'Hindustan Zinc Ltd',
            'type': 'mining_stock',
            'exchange': 'NSE',
            'amc': None,
            'sector': 'Mining & Metals',
            'expense_ratio': None,
            'aum': None,
            'nav': None,
            'current_price': 512.80,
            'daily_change_pct': 0.95,
            'daily_change_abs': 4.83,
            'week_52_high': 588.50,
            'week_52_low': 385.20,
            'volume': 5200000,
            'market_cap': 217500.0,
            'isin': 'INE575A01035',
            'category': 'Mining Stock',
            'risk_score': 5.5,
            'volatility': 22.0,
            'beta': 1.10,
            'sharpe_ratio': 0.92,
            'max_drawdown': -25.0,
            'standard_deviation': 20.0,
            'min_investment': 512.80,
            'sip_eligible': True,
            'recommended_horizon': '5+ years',
            'liquidity_score': 7.8,
            'tax_implications': 'LTCG tax at 12.5% above ₹1.25L; STCG at 20%',
        },
        {
            'symbol': 'COALINDIA',
            'name': 'Coal India Ltd',
            'type': 'mining_stock',
            'exchange': 'NSE',
            'amc': None,
            'sector': 'Mining & Metals',
            'expense_ratio': None,
            'aum': None,
            'nav': None,
            'current_price': 485.60,
            'daily_change_pct': -0.35,
            'daily_change_abs': -1.70,
            'week_52_high': 526.30,
            'week_52_low': 356.80,
            'volume': 8900000,
            'market_cap': 298500.0,
            'isin': 'INE522F01014',
            'category': 'Mining Stock',
            'risk_score': 5.2,
            'volatility': 20.5,
            'beta': 1.05,
            'sharpe_ratio': 0.98,
            'max_drawdown': -22.0,
            'standard_deviation': 18.5,
            'min_investment': 485.60,
            'sip_eligible': True,
            'recommended_horizon': '3-5 years',
            'liquidity_score': 9.2,
            'tax_implications': 'LTCG tax at 12.5% above ₹1.25L; STCG at 20%',
        },
        {
            'symbol': 'JINDALSTEL',
            'name': 'Jindal Steel & Power Ltd',
            'type': 'mining_stock',
            'exchange': 'NSE',
            'amc': None,
            'sector': 'Mining & Metals',
            'expense_ratio': None,
            'aum': None,
            'nav': None,
            'current_price': 892.40,
            'daily_change_pct': 2.10,
            'daily_change_abs': 18.38,
            'week_52_high': 1063.50,
            'week_52_low': 685.30,
            'volume': 7500000,
            'market_cap': 91200.0,
            'isin': 'INE749A01030',
            'category': 'Mining Stock',
            'risk_score': 7.2,
            'volatility': 32.0,
            'beta': 1.52,
            'sharpe_ratio': 0.62,
            'max_drawdown': -40.0,
            'standard_deviation': 29.5,
            'min_investment': 892.40,
            'sip_eligible': True,
            'recommended_horizon': '5+ years',
            'liquidity_score': 8.0,
            'tax_implications': 'LTCG tax at 12.5% above ₹1.25L; STCG at 20%',
        },
    ]
    
    # Special stocks (Financial sector)
    special_stocks = [
        {
            'symbol': 'GOLDLOAN',
            'name': 'Muthoot Finance Ltd',
            'type': 'special_stock',
            'exchange': 'NSE',
            'amc': None,
            'sector': 'Financial Services',
            'expense_ratio': None,
            'aum': None,
            'nav': None,
            'current_price': 1845.60,
            'daily_change_pct': 0.55,
            'daily_change_abs': 10.08,
            'week_52_high': 2156.40,
            'week_52_low': 1485.20,
            'volume': 1800000,
            'market_cap': 185200.0,
            'isin': 'INE528G01035',
            'category': 'Gold Loan / Financial',
            'risk_score': 5.0,
            'volatility': 22.5,
            'beta': 0.95,
            'sharpe_ratio': 1.05,
            'max_drawdown': -24.0,
            'standard_deviation': 20.5,
            'min_investment': 1845.60,
            'sip_eligible': True,
            'recommended_horizon': '3-5 years',
            'liquidity_score': 7.5,
            'tax_implications': 'LTCG tax at 12.5% above ₹1.25L; STCG at 20%',
        },
        {
            'symbol': 'MANAPPURAM',
            'name': 'Manappuram Finance Ltd',
            'type': 'special_stock',
            'exchange': 'NSE',
            'amc': None,
            'sector': 'Financial Services',
            'expense_ratio': None,
            'aum': None,
            'nav': None,
            'current_price': 215.30,
            'daily_change_pct': 0.82,
            'daily_change_abs': 1.75,
            'week_52_high': 258.40,
            'week_52_low': 152.80,
            'volume': 6500000,
            'market_cap': 23150.0,
            'isin': 'INE522D01037',
            'category': 'Gold Loan / Financial',
            'risk_score': 5.5,
            'volatility': 25.0,
            'beta': 1.08,
            'sharpe_ratio': 0.88,
            'max_drawdown': -28.0,
            'standard_deviation': 22.8,
            'min_investment': 215.30,
            'sip_eligible': True,
            'recommended_horizon': '3-5 years',
            'liquidity_score': 8.0,
            'tax_implications': 'LTCG tax at 12.5% above ₹1.25L; STCG at 20%',
        },
    ]
    
    all_assets = gold_etfs + silver_etfs + commodity_etfs + mining_stocks + special_stocks
    
    for asset in all_assets:
        cursor.execute('''
            INSERT INTO assets (symbol, name, type, exchange, amc, sector, expense_ratio, aum, nav,
                current_price, daily_change_pct, daily_change_abs, week_52_high, week_52_low,
                volume, market_cap, isin, category, risk_score, volatility, beta, sharpe_ratio,
                max_drawdown, standard_deviation, min_investment, sip_eligible, recommended_horizon,
                liquidity_score, tax_implications)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            asset['symbol'], asset['name'], asset['type'], asset['exchange'], asset.get('amc'),
            asset['sector'], asset.get('expense_ratio'), asset.get('aum'), asset.get('nav'),
            asset['current_price'], asset['daily_change_pct'], asset['daily_change_abs'],
            asset['week_52_high'], asset['week_52_low'], asset['volume'], asset.get('market_cap'),
            asset.get('isin'), asset['category'], asset['risk_score'], asset['volatility'],
            asset['beta'], asset['sharpe_ratio'], asset['max_drawdown'], asset['standard_deviation'],
            asset['min_investment'], asset['sip_eligible'], asset['recommended_horizon'],
            asset['liquidity_score'], asset['tax_implications']
        ))
    
    # Generate historical price data (1 year)
    asset_ids = [r[0] for r in cursor.execute("SELECT id FROM assets").fetchall()]
    
    for asset_id in asset_ids:
        asset = dict(cursor.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone())
        current = asset['current_price']
        high_52w = asset['week_52_high']
        low_52w = asset['week_52_low']
        
        # Generate 365 days of data
        base_price = current * (0.85 + random.random() * 0.15)
        price = base_price
        
        for i in range(365):
            date = (datetime.now() - timedelta(days=365-i)).strftime('%Y-%m-%d')
            
            # Random walk with mean reversion
            drift = (current - price) * 0.002
            noise = random.gauss(0, current * 0.015)
            price = price + drift + noise
            price = max(low_52w * 0.95, min(high_52w * 1.05, price))
            
            daily_range = price * random.uniform(0.005, 0.03)
            open_p = price + random.uniform(-daily_range/2, daily_range/2)
            high_p = max(price, open_p) + random.uniform(0, daily_range/2)
            low_p = min(price, open_p) - random.uniform(0, daily_range/2)
            close_p = price
            
            volume = int(asset['volume'] * random.uniform(0.4, 1.8))
            
            cursor.execute('''
                INSERT INTO price_history (asset_id, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (asset_id, date, round(open_p, 2), round(high_p, 2), 
                  round(low_p, 2), round(close_p, 2), volume))
    
    # Seed news
    news_items = [
        {
            'title': 'Gold Prices Surge as Global Uncertainty Rises',
            'summary': 'Gold prices have risen sharply amid growing geopolitical tensions and inflation concerns. Analysts suggest this trend may continue as central banks increase gold reserves.',
            'source': 'NSE India',
            'source_url': 'https://www.nseindia.com',
            'category': 'Gold',
            'related_assets': 'GOLDBEES,GOLDETF,ICICIGOLD,HDFCGOLD',
            'sentiment': 'positive',
        },
        {
            'title': 'Silver ETFs See Record Inflows',
            'summary': 'Silver-focused ETFs have witnessed record inflows this quarter as industrial demand picks up alongside investment interest.',
            'source': 'AMFI India',
            'source_url': 'https://www.amfiindia.com',
            'category': 'Silver',
            'related_assets': 'SILVERBEES,SILVERETF,ABSLVSIL',
            'sentiment': 'positive',
        },
        {
            'title': 'Mining Sector Faces Regulatory Headwinds',
            'summary': 'New environmental regulations could impact mining operations across India. Companies are assessing compliance costs and operational changes.',
            'source': 'BSE India',
            'source_url': 'https://www.bseindia.com',
            'category': 'Mining',
            'related_assets': 'TATASTEEL,HINDALCO,NMDC,VEDL',
            'sentiment': 'negative',
        },
        {
            'title': 'Central Banks Increase Gold Reserves',
            'summary': 'Multiple central banks have announced plans to increase their gold reserves, signaling continued confidence in the precious metal as a store of value.',
            'source': 'Angel One',
            'source_url': 'https://www.angelone.in',
            'category': 'Gold',
            'related_assets': 'GOLDBEES,GOLDETF',
            'sentiment': 'positive',
        },
        {
            'title': 'Commodity Markets Volatile Amid Trade Tensions',
            'summary': 'Global commodity markets continue to experience heightened volatility as trade tensions between major economies persist.',
            'source': 'NSE India',
            'source_url': 'https://www.nseindia.com',
            'category': 'Commodities',
            'related_assets': 'CRUDEOIL,COPPERETF',
            'sentiment': 'neutral',
        },
        {
            'title': 'Gold Loan Companies Report Strong Q4 Results',
            'summary': 'Gold loan companies have reported strong quarterly results, driven by increased demand for gold-backed lending products.',
            'source': 'Edelweiss',
            'source_url': 'https://www.edelweissmf.com',
            'category': 'Financial',
            'related_assets': 'GOLDLOAN,MANAPPURAM',
            'sentiment': 'positive',
        },
        {
            'title': 'SEBI Introduces New ETF Disclosure Requirements',
            'summary': 'SEBI has introduced new disclosure requirements for ETFs, aimed at improving transparency and investor protection.',
            'source': 'SEBI',
            'source_url': 'https://www.sebi.gov.in',
            'category': 'Regulatory',
            'related_assets': 'GOLDBEES,GOLDETF,ICICIGOLD,HDFCGOLD,SILVERBEES',
            'sentiment': 'neutral',
        },
        {
            'title': 'Steel Prices Expected to Remain Firm',
            'summary': 'Steel prices are expected to remain firm in the near term due to strong domestic demand and global supply constraints.',
            'source': 'BSE India',
            'source_url': 'https://www.bseindia.com',
            'category': 'Mining',
            'related_assets': 'TATASTEEL,JINDALSTEL',
            'sentiment': 'positive',
        },
    ]
    
    for news in news_items:
        cursor.execute('''
            INSERT INTO news (title, summary, source, source_url, category, related_assets, sentiment, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (news['title'], news['summary'], news['source'], news['source_url'],
              news['category'], news['related_assets'], news['sentiment'],
              (datetime.now() - timedelta(hours=random.randint(1, 48))).isoformat()))
    
    # Create default watchlist
    cursor.execute("INSERT INTO watchlists (name) VALUES (?)", ('Default',))
    
    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
    seed_data()
    print("Database initialized and seeded successfully!")