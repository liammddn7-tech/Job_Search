"""
job_finder.py

Queries the JSearch API (via RapidAPI) daily for remote, part-time roles
in client experience / business development (both salaried and hourly),
and flags listings that look like they'd fit an evening (~7pm-12am ET)
Monday-Friday schedule.

Output: docs/jobs.json  -> full rolling list the dashboard reads
        seen_job_ids.json -> dedup memory so re-runs don't re-add old jobs

Environment variable required:
        RAPIDAPI_KEY  -- your JSearch API key from rapidapi.com
"""

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# CONFIG - edit these to tune your search
# ---------------------------------------------------------------------------

# Each string is a separate search query sent to JSearch. Add/remove/edit
# freely -- more queries = broader coverage but more API calls (free tier
# is ~2500 requests/month via OpenWeb Ninja portal, or check your plan).
SEARCH_QUERIES = [
    "client experience remote part time",
    "business development remote part time",
    "customer success manager remote part time",
    "account manager remote part time",
    "client relations remote part time evening",
]

EMPLOYMENT_TYPES = "PARTTIME"
REMOTE_ONLY = True
COUNTRY = "us"
DATE_POSTED = "3days"        # 'today' | '3days' | 'week' | 'month' | 'all'
NUM_PAGES = 1                 # pages per query (10 results/page)

# Keywords in the job description that suggest an evening shift.
EVENING_KEYWORDS = [
    "evening", "night shift", "2nd shift", "second shift", "swing shift",
    "pm shift", "pm to", "pm-", "7pm", "7 pm", "7:00pm", "7:00 pm",
    "after 5pm", "after 5 pm", "late afternoon", "overnight",
]

# Keywords that suggest hourly (not salaried) pay -- these listings are still
# included, just tagged "hourly-pay" so you can tell at a glance.
HOURLY_KEYWORDS = ["/hr", "/ hour", "per hour", "hourly rate", "hourly pay"]

ROLE_KEYWORDS = [
    "client experience", "business development", "customer success",
    "account manager", "client relations", "client success",
]

DATA_DIR = Path(__file__).parent / "docs"
JOBS_FILE = DATA_DIR / "jobs.json"
SEEN_FILE = Path(__file__).parent / "seen_job_ids.json"

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search-v2"

# ---------------------------------------------------------------------------


def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return default
    return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def search_jsearch(query, api_key):
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }
    params = {
        "query": query,
        "num_pages": str(NUM_PAGES),
        "date_posted": DATE_POSTED,
        "employment_types": EMPLOYMENT_TYPES,
        "remote_jobs_only": "true" if REMOTE_ONLY else "false",
        "country": COUNTRY,
    }
    resp = requests.get(JSEARCH_URL, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") == "ERROR":
        print(f"[warn] API returned an error for query {query!r}: {body.get('error')}")
        return []
    data = body.get("data", {})
    # search-v2 nests results as {"jobs": [...], "cursor": "..."} rather than
    # returning the job list directly under "data".
    if isinstance(data, dict):
        return data.get("jobs", [])
    return data  # fallback in case the shape changes back to a plain list


def score_job(job):
    """Return (score, tags) -- higher score = better match."""
    text = " ".join([
        job.get("job_title", "") or "",
        job.get("job_description", "") or "",
    ]).lower()

    score = 0
    tags = []

    # Salary check
    has_salary = bool(job.get("job_min_salary") or job.get("job_max_salary"))
    is_hourly_period = (job.get("job_salary_period") or "").upper() == "HOUR"
    mentions_hourly_text = any(k in text for k in HOURLY_KEYWORDS)

    if has_salary and not is_hourly_period:
        score += 3
        tags.append("salary-confirmed")
    elif mentions_hourly_text or is_hourly_period:
        score += 1  # still included, just tagged so you can see the pay type
        tags.append("hourly-pay")
    else:
        tags.append("pay-type-unclear")

    # Evening shift check
    if any(k in text for k in EVENING_KEYWORDS):
        score += 3
        tags.append("evening-shift-mentioned")

    # Role relevance
    if any(k in text for k in ROLE_KEYWORDS):
        score += 1

    # Remote confirmation
    if job.get("job_is_remote"):
        score += 1
        tags.append("remote-confirmed")

    return score, tags


def normalize(job):
    score, tags = score_job(job)
    return {
        "id": job.get("job_id"),
        "title": job.get("job_title"),
        "company": job.get("employer_name"),
        "location": job.get("job_location") or job.get("job_country"),
        "is_remote": job.get("job_is_remote"),
        "min_salary": job.get("job_min_salary"),
        "max_salary": job.get("job_max_salary"),
        "salary_period": job.get("job_salary_period"),
        "posted_at": job.get("job_posted_at_datetime_utc") or job.get("job_posted_at"),
        "apply_link": job.get("job_apply_link"),
        "description_snippet": (job.get("job_description") or "")[:400],
        "score": score,
        "tags": tags,
        "first_seen": datetime.now(timezone.utc).isoformat(),
    }


def main():
    api_key = os.environ.get("RAPIDAPI_KEY")
    if not api_key:
        raise SystemExit("Set the RAPIDAPI_KEY environment variable before running.")

    seen_ids = set(load_json(SEEN_FILE, []))
    existing_jobs = load_json(JOBS_FILE, [])

    new_jobs = []
    for query in SEARCH_QUERIES:
        try:
            results = search_jsearch(query, api_key)
        except requests.HTTPError as e:
            print(f"[warn] query failed: {query!r} -- {e}")
            continue

        for raw in results:
            if not isinstance(raw, dict):
                print(f"[warn] unexpected item in results for query {query!r}: {type(raw)} -> {str(raw)[:200]}")
                continue
            job_id = raw.get("job_id")
            if not job_id or job_id in seen_ids:
                continue
            seen_ids.add(job_id)
            new_jobs.append(normalize(raw))

        time.sleep(1)  # be polite to the API / avoid rate limits

    combined = new_jobs + existing_jobs
    # keep a rolling 45-day window so the file doesn't grow forever
    cutoff = time.time() - 45 * 86400
    combined = [
        j for j in combined
        if _parse_ts(j.get("first_seen")) > cutoff
    ]
    combined.sort(key=lambda j: j["score"], reverse=True)

    save_json(JOBS_FILE, combined)
    save_json(SEEN_FILE, list(seen_ids))

    print(f"Added {len(new_jobs)} new job(s). Total tracked: {len(combined)}.")


def _parse_ts(iso_str):
    if not iso_str:
        return 0
    try:
        return datetime.fromisoformat(iso_str).timestamp()
    except ValueError:
        return 0


if __name__ == "__main__":
    main()
