c = open('static/app/index.html', 'r', encoding='utf-8').read()
start = c.find('<script>') + 8
end = c.find('</script>')
js = c[start:end]
lines = js.split('\n')
print('Total JS lines:', len(lines))

# Check for unquoted CSS values in JS object literals
import re
for i, line in enumerate(lines, 1):
    # Check for color:#fff without quotes (invalid JS)
    if re.search(r'color:#fff\}', line):
        print('BUG Line %d: %s' % (i, line.strip()[:120]))
    if re.search(r'color:#fff\",', line):
        pass  # This is fine - quoted
    # Check for any unquoted hash colors in style objects
    matches = re.findall(r'(\w+):#([0-9a-fA-F]{3,8})', line)
    for m in matches:
        # Check if it's inside a quoted string
        context = line[line.find(m[0]+':#'+m[1]):]
        if not context.startswith(m[0]+':"' + '#' + m[1]):
            if '#' + m[1] not in ['fff', '000']:
                pass  # Most are fine inside quoted strings

# Check for specific known issues
if 'color:#fff}' in c:
    print('\nFOUND: unquoted color:#fff in style object')
    idx = c.find('color:#fff}')
    print('Context:', repr(c[max(0,idx-50):idx+50]))