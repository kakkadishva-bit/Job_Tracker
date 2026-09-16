import re

c = open('static/app/index.html', 'r', encoding='utf-8').read()
css_end = c.find('</style>') + 8
before = c[:css_end]
after = c[css_end:]

# Fix unquoted color values in JS
after = after.replace('color:#fff}', 'color:"#fff"}')
after = after.replace('color:#fff,', 'color:"#fff",')
after = after.replace('color:#000}', 'color:"#000"}')

fixed = before + after
open('static/app/index.html', 'w', encoding='utf-8').write(fixed)

remaining = after.count('color:#fff}')
print('Remaining unquoted color:#fff}:', remaining)
print('File saved, size:', len(fixed))