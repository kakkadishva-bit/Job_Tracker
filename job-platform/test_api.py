import requests
import json

BASE = "http://localhost:5000"

def test(name, url, method="GET", data=None):
    try:
        r = getattr(requests, method.lower())(BASE + url, json=data)
        d = r.json()
        print(f"✅ {name}: {r.status_code}")
        return d
    except Exception as e:
        print(f"❌ {name}: {e}")
        return None

# Test API endpoints
print("=" * 60)
print("PreciousMetals AI - API Test Suite")
print("=" * 60)

# Test assets
d = test("GET /api/assets", "/api/assets")
if d:
    print(f"   Found {d['count']} assets")
    for a in d['assets'][:3]:
        print(f"   {a['symbol']}: {a['name']} = Rs{a['current_price']}")

# Test single asset
print()
d = test("GET /api/assets/GOLDBEES", "/api/assets/GOLDBEES")
if d:
    a = d['asset']
    print(f"   {a['symbol']}: Rs{a['current_price']}")
    ti = d['technical_indicators']
    print(f"   RSI: {ti['rsi']}, SMA20: {ti['sma_20']}")
    f = d['forecast']
    print(f"   Forecast: Bullish {f['bullish']}%, Neutral {f['neutral']}%, Bearish {f['bearish']}%")

# Test chart data
print()
d = test("GET /api/assets/GOLDBEES/chart-data", "/api/assets/GOLDBEES/chart-data?range=1Y")
if d:
    print(f"   Prices: {len(d['prices'])} data points")

# Test insights
print()
d = test("GET /api/insights/GOLDBEES", "/api/insights/GOLDBEES")
if d:
    ins = d['insight']
    print(f"   Sentiment: {ins['market_sentiment']}")
    print(f"   Drivers: {len(ins['key_drivers'])} factors")

# Test market overview
print()
d = test("GET /api/insights/market-overview", "/api/insights/market-overview")
if d:
    s = d['summary']
    print(f"   Total assets: {s['total_assets']}")
    print(f"   Gold avg: {s['avg_gold_change']}%")
    print(f"   Gainers: {len(d['top_gainers'])}, Losers: {len(d['top_losers'])}")

# Test news
print()
d = test("GET /api/news", "/api/news")
if d:
    print(f"   News items: {d['count']}")

# Test portfolio
print()
d = test("POST /api/portfolios", "/api/portfolios", "POST", {"name": "Test Portfolio"})
if d:
    pid = d.get('id')
    print(f"   Created portfolio #{pid}")
    
    # Add holding
    test("POST /api/portfolios/1/holdings", f"/api/portfolios/{pid}/holdings", "POST", {
        "symbol": "GOLDBEES", "quantity": 10, "avg_buy_price": 60.0
    })
    
    # Get portfolio
    d = test("GET /api/portfolios", "/api/portfolios")
    if d and d['portfolios']:
        p = d['portfolios'][0]
        print(f"   Portfolio: {p['name']}, Value: Rs{p['current_value']}")

# Test watchlist
print()
test("POST /api/watchlists/1/items", "/api/watchlists/1/items", "POST", {"symbol": "GOLDBEES"})
d = test("GET /api/watchlists", "/api/watchlists")
if d and d['watchlists']:
    wl = d['watchlists'][0]
    print(f"   Watchlist '{wl['name']}': {len(wl['items'])} items")

# Test compare
print()
d = test("GET /api/assets/GOLDBEES/compare", "/api/assets/GOLDBEES/compare?symbols=SILVERBEES,TATASTEEL")
if d:
    print(f"   Compared {len(d['assets'])} assets")

# Test search
print()
d = test("GET /api/assets (search)", "/api/assets?search=gold&type=gold_etf")
if d:
    print(f"   Found {d['count']} gold ETF assets")

# Test admin stats
print()
d = test("GET /api/admin/stats", "/api/admin/stats")
if d:
    for k, v in d.items():
        print(f"   {k}: {v}")

# Test config
print()
d = test("GET /api/config", "/api/config")
if d:
    print(f"   Data sources: {len(d['data_sources'])}")
    print(f"   Disclaimer: {d['disclaimer'][:50]}...")

# Test HTML page
print()
r = requests.get(BASE + "/")
print(f"✅ GET / (HTML): {r.status_code}")
print(f"   Content length: {len(r.text)} chars")
print(f"   Contains React: {'react' in r.text.lower()}")
print(f"   Contains Tailwind: {'tailwindcss' in r.text.lower()}")

print()
print("=" * 60)
print("All API tests completed!")
print("=" * 60)