import requests
r = requests.get('http://localhost:5000/')
checks = {
    'status': r.status_code == 200,
    'has_script_close': '</script>' in r.text,
    'no_broken_script': '<\\/script>' not in r.text,
    'has_color_fix': 'color:"#fff"' in r.text,
    'has_tailwind': 'tailwindcss' in r.text,
    'has_chartjs': 'chart.js' in r.text,
    'has_app_div': 'id="app"' in r.text,
    'has_loadData': 'function loadData' in r.text,
    'has_render': 'function render' in r.text,
}
all_ok = True
for name, ok in checks.items():
    print(('  OK' if ok else 'FAIL') + ': ' + name)
    if not ok:
        all_ok = False
print()
if all_ok:
    print('All checks passed! Page should render correctly.')
else:
    print('Some checks failed.')