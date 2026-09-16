import requests
r = requests.get('http://localhost:5000/')
html = r.text
print("Page size:", len(html))
print("Has DOCTYPE:", "<!DOCTYPE" in html)
print("Has tailwind:", "tailwindcss" in html)
print("Has chart.js:", "chart.js" in html)
print("Has app div:", 'id="app"' in html)
print("Has loadData:", "function loadData" in html)
print("Has render:", "function render" in html)
print("Has mkDashboard:", "function mkDashboard" in html)
print("No optional chaining:", html.count("?.") == 0)
print("No arrow functions:", "=>" not in html)
print("Has API endpoints:", "/api/assets" in html)