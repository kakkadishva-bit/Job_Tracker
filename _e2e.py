import json
import time
import urllib.request
import http.cookiejar

BASE = "http://127.0.0.1:5000"
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def req(path, payload=None, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    if data:
        r.add_header("Content-Type", "application/json")
    try:
        with opener.open(r, timeout=120) as resp:
            body = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body[:300]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body[:300]


t0 = time.time()

# 1) Home page renders the new sections
status, html = req("/")
print("1) GET / ->", status, "| page-jobs:", 'id="page-jobs"' in html,
      "| page-applications:", 'id="page-applications"' in html,
      "| bell:", 'id="navBellWrap"' in html)
assert status == 200

# 2) Live jobs search (no API keys configured -> scraper-based sources only)
status, jobs = req("/api/jobs/search", {"job_title": "Python Developer", "location": "", "limit": 20})
print("2) /api/jobs/search ->", status, "| total:", jobs.get("total"),
      "| sources_used:", jobs.get("sources_used"),
      "| sources_failed:", jobs.get("sources_failed"),
      "| notice:", (jobs.get("notice") or "")[:80])
assert status == 200 and "jobs" in jobs and "sources_used" in jobs
if jobs.get("jobs"):
    j = jobs["jobs"][0]
    print("   first job:", j.get("job_title"), "@", j.get("company_name"),
          "| freshness:", j.get("freshness_label"), "| url:", bool(j.get("job_url")))

# 3) Skill demand
status, demand = req("/api/market/skill-demand", {"job_title": "Python Developer", "sample_size": 20})
print("3) /api/market/skill-demand ->", status, "| sample:", demand.get("sample_size"),
      "| skills:", len(demand.get("in_demand_skills", [])),
      "| warning:", (demand.get("warning") or "")[:60])
assert status == 200 and "in_demand_skills" in demand
for s in demand.get("in_demand_skills", [])[:5]:
    print("   -", s["skill"], s["demand_pct"], "%")

# 4) Applications require login when unauthenticated
status, body = req("/api/applications")
print("4) unauth GET /api/applications ->", status, "(302 redirect to /login expected)")
assert status in (301, 302, 401)

# 5) Signup a verification user (auto-login)
email = "e2e.check+%d@jobagent.test" % int(time.time())
status, out = req("/api/auth/signup", {
    "email": email, "username": "e2echecker%d" % int(time.time()),
    "password": "E2eCheck!2026", "confirm_password": "E2eCheck!2026",
})
print("5) signup ->", status, out.get("success"), out.get("message"))
assert status == 200 and out.get("success")

# 6) Applications CRUD
status, board = req("/api/applications")
print("6) GET /api/applications ->", status, "| total:", board.get("total"))
assert status == 200 and "board" in board

status, created = req("/api/applications", {
    "company": "Acme Corp", "role": "Backend Engineer",
    "location": "Remote", "job_url": "https://example.com/job/1",
    "salary_range": "$90k - $120k", "status": "applied",
})
print("   POST ->", status, created)
assert status == 200 and created.get("id")
app_id = created["id"]

status, upd = req("/api/applications/%d" % app_id, {"status": "interview"}, method="PATCH")
print("   PATCH ->", status, upd)
assert status == 200 and upd.get("current_status") == "interview"

status, board = req("/api/applications")
print("   board after PATCH:", {k: len(v) for k, v in board["board"].items() if v})
assert board["board"].get("interview"), "application should be in interview column"

# 7) Notifications
status, notifs = req("/api/notifications")
print("7) GET /api/notifications ->", status, "| unread:", notifs.get("unread_count"))
assert status == 200 and "unread_count" in notifs
if notifs.get("notifications"):
    nid = notifs["notifications"][0]["id"]
    status, out = req("/api/notifications/%d/read" % nid, {}, method="POST")
    print("   mark one read ->", status, out)
    assert status == 200
status, out = req("/api/notifications/read-all", {}, method="POST")
print("   read-all ->", status, out)
assert status == 200
status, notifs2 = req("/api/notifications")
print("   unread after read-all:", notifs2.get("unread_count"))

print("E2E PASSED in %.1fs" % (time.time() - t0))