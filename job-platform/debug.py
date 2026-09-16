c = open('static/app/index.html', 'r', encoding='utf-8').read()

# Find the main script (last <script> tag)
last_open = c.rfind('<script>')
last_close = c.rfind('</script>')
print('Last <script> at:', last_open)
print('Last </script> at:', last_close)

js = c[last_open:last_close]
print('JS content length:', len(js))
print('First 100 chars:', js[:100])
print('Last 100 chars:', js[-100:])

# Check for syntax errors
print('\n--- Checking for issues ---')
# Check for unquoted property names
import re
# Find color:#fff without quotes in JS (not CSS)
css_end = c.find('</style>')
js_only = c[css_end:]
# Find unquoted object properties
issues = re.findall(r'\{[^}]*color:#fff[^}]*\}', js_only)
for issue in issues[:5]:
    print('Potential issue:', issue[:80])

# Count opening and closing braces in JS
print('Open braces:', js.count('{'))
print('Close braces:', js.count('}'))
print('Open parens:', js.count('('))
print('Close parens:', js.count(')'))