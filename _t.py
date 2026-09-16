import os
import time
import requests

print("HTTP_PROXY=%r HTTPS_PROXY=%r NO_PROXY=%r" % (
    os.environ.get("HTTP_PROXY"), os.environ.get("HTTPS_PROXY"),
    os.environ.get("NO_PROXY")))
print("proxies from env dict:", requests.utils.get_environ_proxies("http://127.0.0.1:1"))

for label, fn in (
    ("GET  /models", lambda: requests.get("http://127.0.0.1:1/models", timeout=1)),
    ("POST /chat", lambda: requests.post("http://127.0.0.1:1/chat/completions", json={}, timeout=1)),
):
    t = time.time()
    try:
        fn()
        print("%s -> no exception %.2fs" % (label, time.time() - t))
    except Exception as e:
        print("%s -> %s %.2fs err=%s" % (label, type(e).__name__, time.time() - t, str(e)[:120]))

t = time.time()
try:
    s = __import__("socket").create_connection(("127.0.0.1", 1), 1)
    s.close()
    print("socket -> connected %.2fs" % (time.time() - t))
except Exception as e:
    print("socket -> %s %.2fs" % (e, time.time() - t))