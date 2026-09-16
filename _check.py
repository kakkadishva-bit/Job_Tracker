import io
import re
from html.parser import HTMLParser

t = io.open("app.py", encoding="utf-8").read()
print("LOGIN ROUTES:")
for i, l in enumerate(t.splitlines()):
    if re.search(r"login_page|def (login|signup)|'/login'|\"/login\"", l):
        print(" ", i + 1, l.strip()[:100])

src = io.open("templates/index.html", encoding="utf-8").read()


class P(HTMLParser):
    VOID = {"br", "img", "input", "meta", "link", "hr", "area", "base",
            "col", "embed", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.errs = []

    def handle_starttag(self, tag, attrs):
        if tag not in P.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in P.VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.errs.append("unclosed <" + self.stack.pop() + ">")
            self.stack.pop()
        else:
            self.errs.append("stray </" + tag + ">")


p = P()
p.feed(src)
print("UNCLOSED AT EOF:", p.stack)
print("ERRORS:", p.errs[:12])
print("has page-jobs:", 'id="page-jobs"' in src,
      "| page-applications:", 'id="page-applications"' in src,
      "| navBellWrap:", 'id="navBellWrap"' in src)