# Evening Shift Job Agent — Setup Guide

This runs a daily search on JSearch for remote, part-time roles in client
experience / business development — salaried and hourly both included — flags
ones that mention an evening schedule, and shows everything on a simple
dashboard page. Use the "Salary confirmed" / "Hourly pay" filters on the
dashboard to narrow down by pay type whenever you want.

## 1. Get a JSearch API key (free)

1. Go to https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch and sign up
   (free account).
2. Subscribe to the **free "Basic" plan** for JSearch (no credit card needed
   for the free tier at time of writing — double check on the page).
3. Copy your API key from the RapidAPI dashboard (it's the same key for every
   API you subscribe to on RapidAPI).

## 2. Create a GitHub repo

1. Create a new **public or private** repo on GitHub, e.g. `evening-job-agent`.
2. Upload all the files from this folder into it (job_finder.py,
   the `.github/workflows/` folder, and the `docs/` folder), preserving the
   folder structure.

## 3. Add your API key as a secret

1. In your repo: **Settings → Secrets and variables → Actions → New repository secret**
2. Name: `RAPIDAPI_KEY`
3. Value: paste the key from step 1.

## 4. Turn on GitHub Pages (this is your dashboard)

1. **Settings → Pages**
2. Under "Build and deployment", set Source to **Deploy from a branch**
3. Branch: `main`, folder: `/docs` → Save
4. GitHub will give you a URL like `https://yourusername.github.io/evening-job-agent/`
   — that's your dashboard. Bookmark it.

## 5. Run it for the first time

You don't have to wait for the schedule — go to the **Actions** tab in your
repo, click **Daily Job Search** on the left, click **Run workflow** → **Run
workflow**. After ~30 seconds, check your dashboard URL.

After that, it runs automatically every weekday morning (11:00 UTC / 7am ET —
edit the `cron:` line in `.github/workflows/daily-job-search.yml` if you want
a different time).

## Tuning your search

Open `job_finder.py` and edit the `SEARCH_QUERIES` list near the top to add,
remove, or reword search terms. You can also edit `EVENING_KEYWORDS` if you
notice the flagging is missing phrasing that shift-based listings actually use.

## Honest limitations

- **No job API can filter by exact shift hours.** The "evening shift
  mentioned" tag is a best-effort keyword scan of the job description — it
  will miss jobs that don't spell out hours, and occasionally flag one that
  isn't really evening-only. Treat the score as a ranking, not a guarantee.
- **Both salaried and hourly listings are included** and tagged accordingly
  ("salary-confirmed" or "hourly-pay") so you can filter by pay type on the
  dashboard, or just eyeball it per listing.
- JSearch's free tier has a monthly request cap. Five queries a day, five
  days a week, is roughly 100 requests/month — comfortably inside free tiers,
  but if you add many more search queries, keep an eye on usage on your
  RapidAPI dashboard.
