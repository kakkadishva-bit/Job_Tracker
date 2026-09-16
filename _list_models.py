"""List models available to the configured key."""
import os, json
from dotenv import load_dotenv
load_dotenv()
import requests

key = os.environ.get("GROQ_API_KEY", "").strip()
r = requests.get("https://api.groq.com/openai/v1/models",
                 headers={"Authorization": "Bearer " + key}, timeout=15)
print("status:", r.status_code)
try:
    data = r.json()
    ids = [m.get("id") for m in data.get("data", [])]
    print("count:", len(ids))
    for i in ids:
        print(" -", i)
except Exception as e:
    print("body:", r.text[:500], e)
