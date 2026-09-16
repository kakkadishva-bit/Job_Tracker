# -*- coding: utf-8 -*-
import io

with io.open("_js_part1.js", encoding="utf-8") as f:
    block = f.read().strip()

path = r"static/js/app.js"
with io.open(path, encoding="utf-8") as f:
    t = f.read()

if "/* ─── Live Jobs / Skill Demand" in t:
    print("ALREADY SPLICED - skipping")
else:
    t = t.rstrip() + "\n\n" + block + "\n"
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(t)
    print("APPENDED. new len:", len(t))