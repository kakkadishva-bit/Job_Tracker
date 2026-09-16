"""
Precious Metals & ETF Investment Intelligence Platform
Main Flask Application
"""
import os
import json
import math
import random
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, jsonify, request, send_from_directory, render_template
from flask_cors import CORS

from config import Config, config_map
from database import get_db, init_db, seed_data

# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.from_object(config_map.get(os.environ.get('FLASK_ENV', 'development'), Config))
CORS(app)

# Initialize database on startup
with app.app_context():
    init_db()
    seed_data()


# ============================================================
# Helper Functions
# ============================================================

def dict_from_row(row):
    """Convert sqlite3.Row to dict"""
    if row is None:
        return None
    return dict(row)


def dicts_from_rows(rows):
    """Convert list of sqlite3.Row to list of dicts"""
    return [dict(r) for r in rows]


def format_currency(value, decimals=2):
    """Format number as currency"""
    if value is None:
        return None
    return round(value, decimals)


def format_volume(vol):
    """Format volume in human readable"""
    if vol is None:
        return None
    if vol >= 10000000:
        return f"{vol/10000000:.2f}Cr"
    elif vol >= 100000:
        return f"{vol/100000:.2f}L"
    elif vol >= 1000:
        return f"{vol/1000:.1f}K"
    return str(vol)


def calculate_bollinger_bands(prices, period=20, num_std=2):
    """Calculate Bollinger Bands"""
    if len(prices) < period:
        return None, None, None
    
    recent = prices[-period:]
    middle = sum(recent) / len(recent)
    variance = sum((p - middle) ** 2 for p in recent) / len(recent)
    std = math.sqrt(variance)
    
    upper = middle + (num_std * std)
    lower = middle - (num_std * std)
    
    return round(upper, 2), round(middle, 2), round(lower, 2)


def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    if len(prices) < period + 1:
        return 50.0
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    
    if len(gains) < period:
        return 50.0
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


def calculate_ema(prices, period):
    """Calculate Exponential Moving Average"""
    if len(prices) < period:
        return prices[-1] if prices else 0
    
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    
    return round(ema, 2)


def calculate_macd(prices):
    """Calculate MACD"""
    if len(prices) < 26:
        return 0, 0, 0
    
    ema12 = calculate_ema(prices, 12)
    ema26 = calculate_ema(prices, 26)
    macd_line = ema12 - ema26
    
    # Simplified signal
    macd_values = []
    for i in range(26, len(prices)):
        e12 = calculate_ema(prices[:i+1], 12)
        e26 = calculate_ema(prices[:i+1], 26)
        macd_values.append(e12 - e26)
    
    signal = sum(macd_values[-9:]) / 9 if len(macd_values) >= 9 else macd_line
    histogram = macd_line - signal
    
    return round(macd_line, 2), round(signal, 2), round(histogram, 2)


def generate_forecast(asset_data, prices):
    """Generate probability-based forecast"""
    if not prices or len(prices) < 30:
        return {
            'bullish': 40, 'neutral': 30, 'bearish': 30,
            'confidence': 35, 'methodology': 'Insufficient historical data'
        }
    
    # Calculate technical indicators
    rsi = calculate_rsi(prices)
    sma_20 = sum(prices[-20:]) / 20 if len(prices) >= 20 else prices[-1]
    sma_50 = sum(prices[-50:]) / 50 if len(prices) >= 50 else sma_20
    current_price = prices[-1]
    
    # Score based on indicators
    score = 0
    
    # RSI signal
    if rsi < 30:
        score += 2  # Oversold, likely bounce
    elif rsi > 70:
        score -= 2  # Overbought, likely pullback
    elif 40 <= rsi <= 60:
        score += 0
    elif rsi < 40:
        score += 1
    else:
        score -= 1
    
    # Moving average signal
    if current_price > sma_20:
        score += 1
    if current_price > sma_50:
        score += 1
    if sma_20 > sma_50:
        score += 1
    elif sma_20 < sma_50:
        score -= 1
    
    # Price momentum (recent 5 days)
    if len(prices) >= 5:
        momentum = (prices[-1] - prices[-5]) / prices[-5] * 100
        if momentum > 2:
            score += 1
        elif momentum < -2:
            score -= 1
    
    # Map score to probabilities
    if score >= 3:
        bullish, neutral, bearish = 55, 25, 20
    elif score >= 2:
        bullish, neutral, bearish = 50, 30, 20
    elif score >= 1:
        bullish, neutral, bearish = 45, 30, 25
    elif score == 0:
        bullish, neutral, bearish = 35, 35, 30
    elif score >= -1:
        bullish, neutral, bearish = 30, 30, 40
    elif score >= -2:
        bullish, neutral, bearish = 25, 30, 45
    else:
        bullish, neutral, bearish = 20, 25, 55
    
    confidence = min(40 + abs(score) * 8, 75)
    
    return {
        'bullish': bullish,
        'neutral': neutral,
        'bearish': bearish,
        'confidence': confidence,
        'methodology': (
            f'Based on RSI ({rsi:.1f}), moving average crossovers (SMA20={sma_20:.2f}, '
            f'SMA50={sma_50:.2f}), and 5-day price momentum. Model uses historical '
            f'pattern recognition with {len(prices)} data points.'
        ),
        'indicators': {
            'rsi': rsi,
            'sma_20': round(sma_20, 2),
            'sma_50': round(sma_50, 2),
            'momentum_5d': round((prices[-1] - prices[-5]) / prices[-5] * 100, 2) if len(prices) >= 5 else 0,
        },
        'limitations': (
            'This forecast is probability-based and does not guarantee future performance. '
            'It relies on historical technical indicators and does not account for sudden '
            'market events, policy changes, or black swan events. Always consult a qualified '
            'financial advisor before making investment decisions.'
        ),
    }


def generate_ai_insight(asset_data, prices, news_items):
    """Generate AI insight for an asset"""
    symbol = asset_data['symbol']
    name = asset_data['name']
    price = asset_data['current_price']
    change = asset_data['daily_change_pct']
    
    rsi = calculate_rsi(prices) if prices else 50
    direction = "up" if change > 0 else "down" if change < 0 else "unchanged"
    
    # Generate insight sections
    today_movement = (
        f"{name} ({symbol}) is currently trading at ₹{price:.2f}, "
        f"{'gaining' if change > 0 else 'losing'} {abs(change):.2f}% today. "
        f"The stock has been {'trending upward' if change > 0 else 'under pressure'} "
        f"in today's session with {'above' if asset_data.get('volume', 0) > asset_data.get('volume', 1) * 1.2 else 'normal'} "
        f"trading volume."
    )
    
    drivers = []
    if asset_data['type'] in ('gold_etf', 'silver_etf'):
        drivers.append("Precious metal spot prices and global demand-supply dynamics")
        drivers.append("US Dollar strength and interest rate expectations")
        drivers.append("Central bank buying patterns and geopolitical tensions")
    elif asset_data['type'] == 'mining_stock':
        drivers.append("Commodity prices and production costs")
        drivers.append("Company-specific operational performance")
        drivers.append("Regulatory environment and environmental compliance")
    else:
        drivers.append("Overall market sentiment and sector rotation")
        drivers.append("Macroeconomic factors including inflation and interest rates")
        drivers.append("Company financials and growth outlook")
    
    sentiment = "cautiously optimistic" if change > 0 else "slightly bearish" if change < -0.5 else "neutral"
    if rsi > 70:
        sentiment = "cautious (overbought territory)"
    elif rsi < 30:
        sentiment = "potentially oversold, possible bounce"
    
    outlook = (
        f"Based on current technical indicators and market conditions, "
        f"the outlook for {name} appears {sentiment}. "
        f"With an RSI of {rsi:.1f}, the asset is currently "
        f"{'in overbought territory' if rsi > 70 else 'in oversold territory' if rsi < 30 else 'in neutral territory'}. "
        f"Key support is near the 52-week low of ₹{asset_data['week_52_low']:.2f} "
        f"and resistance around ₹{asset_data['week_52_high']:.2f}."
    )
    
    risks = [
        "Market volatility and sudden price swings",
        "Changes in monetary policy and interest rates",
        "Geopolitical events affecting commodity markets",
        "Regulatory changes impacting the sector",
        "Currency fluctuations affecting cross-border valuations",
    ]
    
    opportunities = []
    if asset_data['risk_score'] < 5:
        opportunities.append("Lower risk profile suitable for conservative investors")
    if asset_data.get('expense_ratio') and asset_data['expense_ratio'] < 0.5:
        opportunities.append("Competitive expense ratio enhances net returns")
    if change < -1:
        opportunities.append("Recent pullback may present buying opportunity")
    if rsi < 40:
        opportunities.append("Oversold conditions suggest potential mean reversion")
    opportunities.append(f"Recommended investment horizon: {asset_data.get('recommended_horizon', '3-5 years')}")
    
    return {
        'today_movement': today_movement,
        'key_drivers': drivers,
        'market_sentiment': sentiment,
        'historical_trends': outlook,
        'risks': risks[:3],
        'opportunities': opportunities[:3],
        'data_sources': ['NSE India', 'BSE India', 'Technical Analysis'],
        'last_updated': datetime.now().isoformat(),
        'disclaimer': Config.DISCLAIMER,
    }


# ============================================================
# API Routes - Assets
# ============================================================

@app.route('/api/assets', methods=['GET'])
def get_assets():
    """Get all assets with optional filters"""
    conn = get_db()
    cursor = conn.cursor()
    
    asset_type = request.args.get('type')
    sector = request.args.get('sector')
    search = request.args.get('search', '')
    sort_by = request.args.get('sort_by', 'symbol')
    sort_order = request.args.get('sort_order', 'asc')
    min_risk = request.args.get('min_risk', type=float)
    max_risk = request.args.get('max_risk', type=float)
    min_investment = request.args.get('min_investment', type=float)
    sip_eligible = request.args.get('sip_eligible')
    risk_category = request.args.get('risk_category')
    
    query = "SELECT * FROM assets WHERE is_active = 1"
    params = []
    
    if asset_type:
        query += " AND type = ?"
        params.append(asset_type)
    
    if sector:
        query += " AND sector = ?"
        params.append(sector)
    
    if search:
        query += " AND (symbol LIKE ? OR name LIKE ? OR category LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    if min_risk is not None:
        query += " AND risk_score >= ?"
        params.append(min_risk)
    
    if max_risk is not None:
        query += " AND risk_score <= ?"
        params.append(max_risk)
    
    if min_investment is not None:
        query += " AND min_investment <= ?"
        params.append(min_investment)
    
    if sip_eligible is not None:
        query += " AND sip_eligible = ?"
        params.append(1 if sip_eligible.lower() == 'true' else 0)
    
    # Risk category filter
    if risk_category:
        if risk_category == 'low':
            query += " AND risk_score < 4"
        elif risk_category == 'moderate':
            query += " AND risk_score >= 4 AND risk_score < 6"
        elif risk_category == 'high':
            query += " AND risk_score >= 6"
    
    # Sorting
    valid_sorts = ['symbol', 'name', 'current_price', 'daily_change_pct', 'risk_score', 
                   'volume', 'volatility', 'sharpe_ratio', 'market_cap']
    if sort_by in valid_sorts:
        order = 'DESC' if sort_order == 'desc' else 'ASC'
        query += f" ORDER BY {sort_by} {order}"
    else:
        query += " ORDER BY symbol ASC"
    
    cursor.execute(query, params)
    assets = dicts_from_rows(cursor.fetchall())
    conn.close()
    
    # Add computed fields
    for asset in assets:
        if asset['week_52_high'] and asset['week_52_low'] and asset['current_price']:
            range_52 = asset['week_52_high'] - asset['week_52_low']
            if range_52 > 0:
                asset['price_position_52w'] = round(
                    ((asset['current_price'] - asset['week_52_low']) / range_52) * 100, 1
                )
            else:
                asset['price_position_52w'] = 50
        else:
            asset['price_position_52w'] = 50
        
        asset['volume_formatted'] = format_volume(asset['volume'])
    
    return jsonify({
        'assets': assets,
        'count': len(assets),
        'last_updated': datetime.now().isoformat(),
        'source': 'NSE India / BSE India',
    })


@app.route('/api/assets/<symbol>', methods=['GET'])
def get_asset(symbol):
    """Get single asset details"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM assets WHERE symbol = ? AND is_active = 1", (symbol,))
    asset = dict_from_row(cursor.fetchone())
    
    if not asset:
        conn.close()
        return jsonify({'error': 'Asset not found'}), 404
    
    # Get price history
    cursor.execute(
        "SELECT * FROM price_history WHERE asset_id = ? ORDER BY date ASC",
        (asset['id'],)
    )
    price_history = dicts_from_rows(cursor.fetchall())
    conn.close()
    
    prices = [p['close'] for p in price_history if p['close']]
    
    # Calculate technical indicators
    rsi = calculate_rsi(prices)
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(prices) if len(prices) >= 20 else (None, None, None)
    macd_line, macd_signal, macd_histogram = calculate_macd(prices) if len(prices) >= 26 else (0, 0, 0)
    
    sma_20 = round(sum(prices[-20:]) / 20, 2) if len(prices) >= 20 else None
    sma_50 = round(sum(prices[-50:]) / 50, 2) if len(prices) >= 50 else None
    
    # Generate forecast
    forecast = generate_forecast(asset, prices)
    
    # 52-week position
    range_52 = asset['week_52_high'] - asset['week_52_low']
    price_position = round(((asset['current_price'] - asset['week_52_low']) / range_52) * 100, 1) if range_52 > 0 else 50
    
    return jsonify({
        'asset': asset,
        'technical_indicators': {
            'rsi': rsi,
            'bollinger_bands': {'upper': bb_upper, 'middle': bb_middle, 'lower': bb_lower},
            'macd': {'line': macd_line, 'signal': macd_signal, 'histogram': macd_histogram},
            'sma_20': sma_20,
            'sma_50': sma_50,
        },
        'forecast': forecast,
        'price_position_52w': price_position,
        'price_history': price_history[-365:],
        'last_updated': datetime.now().isoformat(),
        'data_source': 'NSE India',
    })


@app.route('/api/assets/<symbol>/chart-data', methods=['GET'])
def get_chart_data(symbol):
    """Get chart data for different time ranges"""
    conn = get_db()
    cursor = conn.cursor()
    
    range_param = request.args.get('range', '1Y')
    chart_type = request.args.get('type', 'line')
    
    cursor.execute("SELECT id FROM assets WHERE symbol = ?", (symbol,))
    asset_row = cursor.fetchone()
    
    if not asset_row:
        conn.close()
        return jsonify({'error': 'Asset not found'}), 404
    
    asset_id = asset_row[0]
    
    # Determine date range
    days_map = {
        '1D': 1, '1W': 7, '1M': 30, '3M': 90,
        '6M': 180, '1Y': 365, '5Y': 365, 'MAX': 365
    }
    days = days_map.get(range_param, 365)
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    cursor.execute(
        "SELECT * FROM price_history WHERE asset_id = ? AND date >= ? ORDER BY date ASC",
        (asset_id, start_date)
    )
    history = dicts_from_rows(cursor.fetchall())
    conn.close()
    
    prices = [h['close'] for h in history if h['close']]
    
    # Calculate moving averages for overlay
    sma_20_data = []
    sma_50_data = []
    bb_data = []
    
    for i in range(len(prices)):
        if i >= 19:
            sma20 = sum(prices[i-19:i+1]) / 20
            sma_20_data.append({'date': history[i]['date'], 'value': round(sma20, 2)})
        else:
            sma_20_data.append({'date': history[i]['date'], 'value': None})
        
        if i >= 49:
            sma50 = sum(prices[i-49:i+1]) / 50
            sma_50_data.append({'date': history[i]['date'], 'value': round(sma50, 2)})
        else:
            sma_50_data.append({'date': history[i]['date'], 'value': None})
        
        if i >= 19:
            window = prices[i-19:i+1]
            mid = sum(window) / 20
            var = sum((p - mid) ** 2 for p in window) / 20
            std = math.sqrt(var)
            bb_data.append({
                'date': history[i]['date'],
                'upper': round(mid + 2 * std, 2),
                'middle': round(mid, 2),
                'lower': round(mid - 2 * std, 2),
            })
        else:
            bb_data.append({'date': history[i]['date'], 'upper': None, 'middle': None, 'lower': None})
    
    # Calculate RSI series
    rsi_data = []
    for i in range(len(prices)):
        if i >= 14:
            gains = []
            losses = []
            for j in range(i-13, i+1):
                diff = prices[j] - prices[j-1]
                gains.append(max(diff, 0))
                losses.append(max(-diff, 0))
            ag = sum(gains) / 14
            al = sum(losses) / 14
            if al == 0:
                rsi_val = 100
            else:
                rsi_val = 100 - (100 / (1 + ag / al))
            rsi_data.append({'date': history[i]['date'], 'value': round(rsi_val, 2)})
        else:
            rsi_data.append({'date': history[i]['date'], 'value': 50})
    
    # Calculate MACD series
    macd_data = []
    for i in range(len(prices)):
        if i >= 25:
            e12 = calculate_ema(prices[:i+1], 12)
            e26 = calculate_ema(prices[:i+1], 26)
            macd_val = e12 - e26
            macd_data.append({'date': history[i]['date'], 'macd': round(macd_val, 2), 'signal': 0})
        else:
            macd_data.append({'date': history[i]['date'], 'macd': 0, 'signal': 0})
    
    return jsonify({
        'prices': history,
        'sma_20': sma_20_data,
        'sma_50': sma_50_data,
        'bollinger_bands': bb_data,
        'rsi': rsi_data,
        'macd': macd_data,
        'range': range_param,
    })


@app.route('/api/assets/<symbol>/compare', methods=['GET'])
def compare_assets(symbol):
    """Compare multiple assets"""
    symbols = request.args.get('symbols', '').split(',')
    symbols = [s.strip() for s in symbols if s.strip()]
    if symbol not in symbols:
        symbols.insert(0, symbol)
    
    conn = get_db()
    cursor = conn.cursor()
    
    results = []
    for sym in symbols[:5]:
        cursor.execute("SELECT * FROM assets WHERE symbol = ?", (sym,))
        asset = dict_from_row(cursor.fetchone())
        if asset:
            # Get 30-day performance
            cursor.execute(
                """SELECT close FROM price_history WHERE asset_id = ? 
                   ORDER BY date DESC LIMIT 30""",
                (asset['id'],)
            )
            recent = [r[0] for r in cursor.fetchall() if r[0]]
            if len(recent) >= 2:
                asset['performance_30d'] = round((recent[0] - recent[-1]) / recent[-1] * 100, 2)
            else:
                asset['performance_30d'] = 0
            results.append(asset)
    
    conn.close()
    
    return jsonify({
        'assets': results,
        'last_updated': datetime.now().isoformat(),
    })


@app.route('/api/assets', methods=['POST'])
def create_asset():
    """Admin: Create new asset"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    required = ['symbol', 'name', 'type']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO assets (symbol, name, type, exchange, amc, sector, expense_ratio, 
                aum, nav, current_price, daily_change_pct, daily_change_abs,
                week_52_high, week_52_low, volume, market_cap, isin, category,
                risk_score, volatility, beta, sharpe_ratio, max_drawdown, standard_deviation,
                min_investment, sip_eligible, recommended_horizon, liquidity_score, tax_implications)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['symbol'], data['name'], data['type'],
            data.get('exchange', 'NSE'), data.get('amc'), data.get('sector'),
            data.get('expense_ratio'), data.get('aum'), data.get('nav'),
            data.get('current_price', 0), data.get('daily_change_pct', 0),
            data.get('daily_change_abs', 0), data.get('week_52_high', 0),
            data.get('week_52_low', 0), data.get('volume', 0),
            data.get('market_cap'), data.get('isin'), data.get('category', ''),
            data.get('risk_score', 5), data.get('volatility', 15),
            data.get('beta', 1.0), data.get('sharpe_ratio', 0.8),
            data.get('max_drawdown', -20), data.get('standard_deviation', 15),
            data.get('min_investment', 100), data.get('sip_eligible', True),
            data.get('recommended_horizon', '3-5 years'),
            data.get('liquidity_score', 7), data.get('tax_implications', '')
        ))
        
        asset_id = cursor.lastrowid
        conn.commit()
        
        # Audit log
        cursor.execute(
            "INSERT INTO audit_log (action, entity, entity_id, details) VALUES (?, ?, ?, ?)",
            ('CREATE', 'asset', asset_id, f"Created asset {data['symbol']}")
        )
        conn.commit()
        
        conn.close()
        return jsonify({'id': asset_id, 'symbol': data['symbol'], 'message': 'Asset created'}), 201
        
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 400


@app.route('/api/assets/<int:asset_id>', methods=['PUT'])
def update_asset(asset_id):
    """Admin: Update asset"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Build update query dynamically
    allowed_fields = [
        'name', 'type', 'exchange', 'amc', 'sector', 'expense_ratio',
        'aum', 'nav', 'current_price', 'daily_change_pct', 'daily_change_abs',
        'week_52_high', 'week_52_low', 'volume', 'market_cap', 'isin',
        'category', 'risk_score', 'volatility', 'beta', 'sharpe_ratio',
        'max_drawdown', 'standard_deviation', 'min_investment', 'sip_eligible',
        'recommended_horizon', 'liquidity_score', 'tax_implications',
        'is_active', 'admin_notes'
    ]
    
    updates = []
    params = []
    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])
    
    if not updates:
        conn.close()
        return jsonify({'error': 'No valid fields to update'}), 400
    
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(asset_id)
    
    query = f"UPDATE assets SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    
    # Audit log
    cursor.execute(
        "INSERT INTO audit_log (action, entity, entity_id, details) VALUES (?, ?, ?, ?)",
        ('UPDATE', 'asset', asset_id, json.dumps(data))
    )
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Asset updated successfully'})


@app.route('/api/assets/<int:asset_id>', methods=['DELETE'])
def delete_asset(asset_id):
    """Admin: Soft delete asset"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE assets SET is_active = 0, updated_at = ? WHERE id = ?",
                   (datetime.now().isoformat(), asset_id))
    cursor.execute(
        "INSERT INTO audit_log (action, entity, entity_id, details) VALUES (?, ?, ?, ?)",
        ('DELETE', 'asset', asset_id, 'Soft deleted asset')
    )
    conn.commit()
    conn.close()
    return jsonify({'message': 'Asset deactivated'})


# ============================================================
# API Routes - AI Insights
# ============================================================

@app.route('/api/insights/<symbol>', methods=['GET'])
def get_insights(symbol):
    """Get AI insights for an asset"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM assets WHERE symbol = ?", (symbol,))
    asset = dict_from_row(cursor.fetchone())
    
    if not asset:
        conn.close()
        return jsonify({'error': 'Asset not found'}), 404
    
    cursor.execute(
        "SELECT * FROM price_history WHERE asset_id = ? ORDER BY date ASC",
        (asset['id'],)
    )
    prices = [r['close'] for r in cursor.fetchall() if r['close']]
    
    # Get related news
    cursor.execute("SELECT * FROM news WHERE related_assets LIKE ? ORDER BY published_at DESC LIMIT 5",
                   (f"%{symbol}%",))
    news = dicts_from_rows(cursor.fetchall())
    
    insight = generate_ai_insight(asset, prices, news)
    
    conn.close()
    
    return jsonify({
        'symbol': symbol,
        'insight': insight,
        'related_news': news,
        'generated_at': datetime.now().isoformat(),
    })


@app.route('/api/insights/market-overview', methods=['GET'])
def get_market_overview():
    """Get market overview insights"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM assets WHERE is_active = 1")
    assets = dicts_from_rows(cursor.fetchall())
    
    # Market summary
    gold_assets = [a for a in assets if a['type'] == 'gold_etf']
    silver_assets = [a for a in assets if a['type'] == 'silver_etf']
    mining_assets = [a for a in assets if a['type'] == 'mining_stock']
    
    avg_gold_change = sum(a['daily_change_pct'] for a in gold_assets) / len(gold_assets) if gold_assets else 0
    avg_silver_change = sum(a['daily_change_pct'] for a in silver_assets) / len(silver_assets) if silver_assets else 0
    avg_mining_change = sum(a['daily_change_pct'] for a in mining_assets) / len(mining_assets) if mining_assets else 0
    
    # Top gainers and losers
    sorted_assets = sorted(assets, key=lambda x: x['daily_change_pct'], reverse=True)
    top_gainers = sorted_assets[:5]
    top_losers = sorted_assets[-5:][::-1] if len(sorted_assets) >= 5 else []
    
    # Most active
    most_active = sorted(assets, key=lambda x: x['volume'] or 0, reverse=True)[:5]
    
    # Risk distribution
    low_risk = sum(1 for a in assets if a['risk_score'] < 4)
    med_risk = sum(1 for a in assets if 4 <= a['risk_score'] < 6)
    high_risk = sum(1 for a in assets if a['risk_score'] >= 6)
    
    conn.close()
    
    return jsonify({
        'market_status': 'open' if datetime.now().hour < 15 and datetime.now().hour >= 9 else 'closed',
        'summary': {
            'total_assets': len(assets),
            'avg_gold_change': round(avg_gold_change, 2),
            'avg_silver_change': round(avg_silver_change, 2),
            'avg_mining_change': round(avg_mining_change, 2),
        },
        'top_gainers': [{'symbol': a['symbol'], 'name': a['name'], 'change': a['daily_change_pct'], 'price': a['current_price']} for a in top_gainers],
        'top_losers': [{'symbol': a['symbol'], 'name': a['name'], 'change': a['daily_change_pct'], 'price': a['current_price']} for a in top_losers],
        'most_active': [{'symbol': a['symbol'], 'name': a['name'], 'volume': a['volume'], 'price': a['current_price']} for a in most_active],
        'risk_distribution': {'low': low_risk, 'moderate': med_risk, 'high': high_risk},
        'last_updated': datetime.now().isoformat(),
    })


# ============================================================
# API Routes - News
# ============================================================

@app.route('/api/news', methods=['GET'])
def get_news():
    """Get news with optional filters"""
    conn = get_db()
    cursor = conn.cursor()
    
    category = request.args.get('category')
    asset_symbol = request.args.get('asset')
    limit = request.args.get('limit', 20, type=int)
    
    query = "SELECT * FROM news"
    params = []
    conditions = []
    
    if category:
        conditions.append("category = ?")
        params.append(category)
    
    if asset_symbol:
        conditions.append("related_assets LIKE ?")
        params.append(f"%{asset_symbol}%")
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY published_at DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    news = dicts_from_rows(cursor.fetchall())
    conn.close()
    
    return jsonify({
        'news': news,
        'count': len(news),
        'last_updated': datetime.now().isoformat(),
    })


# ============================================================
# API Routes - Portfolio
# ============================================================

@app.route('/api/portfolios', methods=['GET'])
def get_portfolios():
    """Get all portfolios"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM portfolios ORDER BY created_at DESC")
    portfolios = dicts_from_rows(cursor.fetchall())
    
    for portfolio in portfolios:
        # Get holdings summary
        cursor.execute("""
            SELECT ph.*, a.symbol, a.name, a.current_price, a.daily_change_pct, a.type, a.category
            FROM portfolio_holdings ph
            JOIN assets a ON ph.asset_id = a.id
            WHERE ph.portfolio_id = ?
        """, (portfolio['id'],))
        holdings = dicts_from_rows(cursor.fetchall())
        
        total_invested = sum(h['quantity'] * h['avg_buy_price'] for h in holdings)
        current_value = sum(h['quantity'] * (h['current_price'] or 0) for h in holdings)
        pnl = current_value - total_invested
        pnl_pct = (pnl / total_invested * 100) if total_invested > 0 else 0
        
        portfolio['holdings'] = holdings
        portfolio['total_invested'] = round(total_invested, 2)
        portfolio['current_value'] = round(current_value, 2)
        portfolio['pnl'] = round(pnl, 2)
        portfolio['pnl_pct'] = round(pnl_pct, 2)
        portfolio['holdings_count'] = len(holdings)
    
    conn.close()
    return jsonify({'portfolios': portfolios})


@app.route('/api/portfolios', methods=['POST'])
def create_portfolio():
    """Create a new portfolio"""
    data = request.get_json()
    name = data.get('name', 'New Portfolio')
    description = data.get('description', '')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO portfolios (name, description) VALUES (?, ?)", (name, description))
    portfolio_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'id': portfolio_id, 'name': name, 'message': 'Portfolio created'}), 201


@app.route('/api/portfolios/<int:portfolio_id>', methods=['PUT'])
def update_portfolio(portfolio_id):
    """Update portfolio"""
    data = request.get_json()
    conn = get_db()
    cursor = conn.cursor()
    
    updates = []
    params = []
    if 'name' in data:
        updates.append("name = ?")
        params.append(data['name'])
    if 'description' in data:
        updates.append("description = ?")
        params.append(data['description'])
    
    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(portfolio_id)
        cursor.execute(f"UPDATE portfolios SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    
    conn.close()
    return jsonify({'message': 'Portfolio updated'})


@app.route('/api/portfolios/<int:portfolio_id>', methods=['DELETE'])
def delete_portfolio(portfolio_id):
    """Delete portfolio and its holdings"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM portfolio_holdings WHERE portfolio_id = ?", (portfolio_id,))
    cursor.execute("DELETE FROM portfolios WHERE id = ?", (portfolio_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Portfolio deleted'})


@app.route('/api/portfolios/<int:portfolio_id>/holdings', methods=['POST'])
def add_holding(portfolio_id):
    """Add holding to portfolio"""
    data = request.get_json()
    symbol = data.get('symbol')
    quantity = data.get('quantity', 0)
    avg_buy_price = data.get('avg_buy_price', 0)
    investment_type = data.get('investment_type', 'lumpsum')
    sip_amount = data.get('sip_amount')
    sip_frequency = data.get('sip_frequency')
    notes = data.get('notes', '')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get asset ID
    cursor.execute("SELECT id FROM assets WHERE symbol = ?", (symbol,))
    asset_row = cursor.fetchone()
    if not asset_row:
        conn.close()
        return jsonify({'error': 'Asset not found'}), 404
    
    asset_id = asset_row[0]
    
    # Check if already exists
    cursor.execute(
        "SELECT id FROM portfolio_holdings WHERE portfolio_id = ? AND asset_id = ?",
        (portfolio_id, asset_id)
    )
    existing = cursor.fetchone()
    
    if existing:
        # Update existing holding
        cursor.execute("""
            UPDATE portfolio_holdings 
            SET quantity = ?, avg_buy_price = ?, investment_type = ?,
                sip_amount = ?, sip_frequency = ?, notes = ?
            WHERE id = ?
        """, (quantity, avg_buy_price, investment_type, sip_amount, sip_frequency, notes, existing[0]))
    else:
        cursor.execute("""
            INSERT INTO portfolio_holdings 
            (portfolio_id, asset_id, quantity, avg_buy_price, investment_type, sip_amount, sip_frequency, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (portfolio_id, asset_id, quantity, avg_buy_price, investment_type, sip_amount, sip_frequency, notes))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Holding added/updated'}), 201


@app.route('/api/portfolios/<int:portfolio_id>/holdings/<int:holding_id>', methods=['DELETE'])
def remove_holding(portfolio_id, holding_id):
    """Remove holding from portfolio"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM portfolio_holdings WHERE id = ? AND portfolio_id = ?",
                   (holding_id, portfolio_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Holding removed'})


@app.route('/api/portfolios/<int:portfolio_id>/sip-simulation', methods=['POST'])
def simulate_sip(portfolio_id):
    """Simulate SIP investment"""
    data = request.get_json()
    monthly_amount = data.get('monthly_amount', 1000)
    months = data.get('months', 12)
    symbol = data.get('symbol')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, current_price FROM assets WHERE symbol = ?", (symbol,))
    asset = cursor.fetchone()
    conn.close()
    
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404
    
    current_price = asset[1]
    simulation = []
    total_units = 0
    total_invested = 0
    
    for i in range(months):
        # Simulate price fluctuation
        price = current_price * (1 + random.uniform(-0.05, 0.05))
        units = monthly_amount / price
        total_units += units
        total_invested += monthly_amount
        current_value = total_units * price
        
        simulation.append({
            'month': i + 1,
            'price': round(price, 2),
            'units': round(units, 4),
            'total_units': round(total_units, 4),
            'total_invested': total_invested,
            'current_value': round(current_value, 2),
            'pnl': round(current_value - total_invested, 2),
        })
    
    return jsonify({
        'simulation': simulation,
        'summary': {
            'total_invested': total_invested,
            'final_value': simulation[-1]['current_value'] if simulation else 0,
            'total_return': simulation[-1]['pnl'] if simulation else 0,
            'return_pct': round(simulation[-1]['pnl'] / total_invested * 100, 2) if simulation and total_invested > 0 else 0,
        }
    })


# ============================================================
# API Routes - Watchlist
# ============================================================

@app.route('/api/watchlists', methods=['GET'])
def get_watchlists():
    """Get all watchlists with items"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM watchlists")
    watchlists = dicts_from_rows(cursor.fetchall())
    
    for wl in watchlists:
        cursor.execute("""
            SELECT wi.*, a.symbol, a.name, a.current_price, a.daily_change_pct, 
                   a.type, a.category, a.risk_score, a.week_52_high, a.week_52_low
            FROM watchlist_items wi
            JOIN assets a ON wi.asset_id = a.id
            WHERE wi.watchlist_id = ?
            ORDER BY wi.added_at DESC
        """, (wl['id'],))
        wl['items'] = dicts_from_rows(cursor.fetchall())
    
    conn.close()
    return jsonify({'watchlists': watchlists})


@app.route('/api/watchlists', methods=['POST'])
def create_watchlist():
    """Create a watchlist"""
    data = request.get_json()
    name = data.get('name', 'New Watchlist')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO watchlists (name) VALUES (?)", (name,))
    wl_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'id': wl_id, 'name': name}), 201


@app.route('/api/watchlists/<int:wl_id>/items', methods=['POST'])
def add_watchlist_item(wl_id):
    """Add item to watchlist"""
    data = request.get_json()
    symbol = data.get('symbol')
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM assets WHERE symbol = ?", (symbol,))
    asset_row = cursor.fetchone()
    if not asset_row:
        conn.close()
        return jsonify({'error': 'Asset not found'}), 404
    
    # Check duplicate
    cursor.execute(
        "SELECT id FROM watchlist_items WHERE watchlist_id = ? AND asset_id = ?",
        (wl_id, asset_row[0])
    )
    if cursor.fetchone():
        conn.close()
        return jsonify({'message': 'Already in watchlist'})
    
    cursor.execute("""
        INSERT INTO watchlist_items (watchlist_id, asset_id, notes, tags, 
            alert_price_high, alert_price_low, alert_volume_spike, alert_risk_change)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (wl_id, asset_row[0], data.get('notes', ''), data.get('tags', ''),
          data.get('alert_price_high'), data.get('alert_price_low'),
          data.get('alert_volume_spike', False), data.get('alert_risk_change', False)))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Added to watchlist'}), 201


@app.route('/api/watchlists/<int:wl_id>/items/<int:item_id>', methods=['DELETE'])
def remove_watchlist_item(wl_id, item_id):
    """Remove item from watchlist"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watchlist_items WHERE id = ? AND watchlist_id = ?",
                   (item_id, wl_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Removed from watchlist'})


@app.route('/api/watchlists/<int:wl_id>/items/<int:item_id>', methods=['PUT'])
def update_watchlist_item(wl_id, item_id):
    """Update watchlist item alerts"""
    data = request.get_json()
    conn = get_db()
    cursor = conn.cursor()
    
    updates = []
    params = []
    for field in ['notes', 'tags', 'alert_price_high', 'alert_price_low',
                  'alert_volume_spike', 'alert_risk_change']:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])
    
    if updates:
        params.extend([item_id, wl_id])
        cursor.execute(
            f"UPDATE watchlist_items SET {', '.join(updates)} WHERE id = ? AND watchlist_id = ?",
            params
        )
        conn.commit()
    
    conn.close()
    return jsonify({'message': 'Watchlist item updated'})


@app.route('/api/watchlists/<int:wl_id>', methods=['DELETE'])
def delete_watchlist(wl_id):
    """Delete watchlist"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watchlist_items WHERE watchlist_id = ?", (wl_id,))
    cursor.execute("DELETE FROM watchlists WHERE id = ?", (wl_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Watchlist deleted'})


# ============================================================
# API Routes - Alerts
# ============================================================

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get all active alerts"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT al.*, a.symbol, a.name, a.current_price
        FROM alerts al
        JOIN assets a ON al.asset_id = a.id
        WHERE al.is_active = 1
        ORDER BY al.created_at DESC
    """)
    alerts = dicts_from_rows(cursor.fetchall())
    conn.close()
    
    return jsonify({'alerts': alerts})


@app.route('/api/alerts', methods=['POST'])
def create_alert():
    """Create price/volume alert"""
    data = request.get_json()
    symbol = data.get('symbol')
    alert_type = data.get('alert_type')
    threshold = data.get('threshold_value')
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM assets WHERE symbol = ?", (symbol,))
    asset_row = cursor.fetchone()
    if not asset_row:
        conn.close()
        return jsonify({'error': 'Asset not found'}), 404
    
    cursor.execute(
        "INSERT INTO alerts (asset_id, alert_type, threshold_value) VALUES (?, ?, ?)",
        (asset_row[0], alert_type, threshold)
    )
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'id': alert_id, 'message': 'Alert created'}), 201


@app.route('/api/alerts/<int:alert_id>', methods=['DELETE'])
def delete_alert(alert_id):
    """Delete alert"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Alert deleted'})


# ============================================================
# API Routes - Admin
# ============================================================

@app.route('/api/admin/assets', methods=['GET'])
def admin_get_assets():
    """Admin: Get all assets including inactive"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM assets ORDER BY symbol")
    assets = dicts_from_rows(cursor.fetchall())
    conn.close()
    return jsonify({'assets': assets, 'count': len(assets)})


@app.route('/api/admin/audit-log', methods=['GET'])
def get_audit_log():
    """Get audit log"""
    limit = request.args.get('limit', 50, type=int)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,))
    logs = dicts_from_rows(cursor.fetchall())
    conn.close()
    return jsonify({'logs': logs})


@app.route('/api/admin/stats', methods=['GET'])
def get_admin_stats():
    """Get platform statistics"""
    conn = get_db()
    cursor = conn.cursor()
    
    stats = {}
    cursor.execute("SELECT COUNT(*) FROM assets WHERE is_active = 1")
    stats['active_assets'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM assets WHERE is_active = 0")
    stats['inactive_assets'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM portfolios")
    stats['portfolios'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM watchlist_items")
    stats['watchlist_items'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM news")
    stats['news_items'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM alerts WHERE is_active = 1")
    stats['active_alerts'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM audit_log")
    stats['audit_entries'] = cursor.fetchone()[0]
    
    conn.close()
    return jsonify(stats)


# ============================================================
# API Routes - Config
# ============================================================

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get platform configuration"""
    return jsonify({
        'data_sources': Config.DATA_SOURCES,
        'disclaimer': Config.DISCLAIMER,
        'asset_types': ['gold_etf', 'silver_etf', 'commodity_etf', 'mining_stock', 'special_stock'],
        'risk_categories': ['low', 'moderate', 'high'],
        'sectors': ['Gold', 'Silver', 'Commodities', 'Mining & Metals', 'Financial Services'],
    })


# ============================================================
# Serve Frontend
# ============================================================

@app.route('/')
def index():
    """Serve main page - use send_from_directory to avoid Jinja2 parsing"""
    return send_from_directory(os.path.join(app.static_folder, 'app'), 'index.html')


@app.route('/<path:path>')
def catch_all(path):
    """Catch-all for SPA routing"""
    if path.startswith('api/'):
        return jsonify({'error': 'Not found'}), 404
    if os.path.exists(os.path.join(app.static_folder, 'app', path)):
        return send_from_directory(os.path.join(app.static_folder, 'app'), path)
    return send_from_directory(os.path.join(app.static_folder, 'app'), 'index.html')


# ============================================================
# Run Application
# ============================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)