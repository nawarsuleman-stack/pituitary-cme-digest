# Pituitary & Adrenal CME Digest — automated daily site

This runs itself: a GitHub Actions job fetches real PubMed abstracts every
day, has Claude triage/summarize them (grounded only in what was actually
fetched — see MASTER_PROMPT.md for the guardrails), and republishes a static
page via GitHub Pages. No server to maintain, and it's free within GitHub's
standard free-tier Actions minutes and Pages hosting.

## One-time setup (about 10 minutes)

1. **Create a new GitHub repo** (public or private — Pages works with both on
   a paid plan; private repos need GitHub Pro/Team/Enterprise for Pages, so
   if you want to stay free, make it public — nothing sensitive is in here,
   it's just published medical literature summaries).

2. **Push these files** to that repo (this whole folder, as-is).

3. **Add two repository secrets** (Settings → Secrets and variables →
   Actions → New repository secret):
   - `ANTHROPIC_API_KEY` — your Anthropic API key from console.anthropic.com.
     This is billed per API call (not your claude.ai subscription) — each
     daily run is one API call, roughly a cent or two depending on how many
     candidate abstracts get fetched that day.
   - `NCBI_API_KEY` — optional but recommended. Free, get one at
     https://www.ncbi.nlm.nih.gov/account/settings/ (raises PubMed's rate
     limit from 3 to 10 requests/second, avoids throttling on busy days).

4. **Enable GitHub Pages**: Settings → Pages → Source: "Deploy from a
   branch" → Branch: `main` → Folder: `/docs` → Save. Your site will be at
   `https://<your-username>.github.io/<repo-name>/`.

5. **Trigger the first run manually**: Actions tab → "Daily pituitary/adrenal
   CME digest" → Run workflow. This builds the first real page (don't wait
   for the schedule to test it).

That's it — after that, it rebuilds itself daily at the scheduled time with
no further action from you.

## How the pieces fit together

- `scripts/fetch_pubmed.py` — queries PubMed's E-utilities directly for the
  pituitary/adrenal topic list, over a rolling 10-year window, and pulls the
  real title/abstract/journal/DOI for each hit. Excludes anything already in
  `data/history.json` from re-appearing.
- `scripts/build_digest.py` — sends those real abstracts to the Anthropic API
  with `MASTER_PROMPT.md` as the system prompt. The model may only select
  from and summarize the abstracts it was given — it cannot introduce a
  paper or claim that wasn't in the fetched data. After the model responds,
  the script cross-checks every returned PMID/DOI against the actual fetched
  records before allowing it onto the site, as a hard guard against
  fabrication.
- `scripts/render_site.py` — turns the verified digest + full history into
  `docs/index.html`, which GitHub Pages serves as-is.
- `data/history.json` — the permanent record: every PMID ever used (so
  nothing repeats) and every past session (so the site's "past sessions"
  panel is always accurate). This file is the actual persistence layer —
  it lives in the repo, not in any one browser, so it's the same for you on
  any device.

## Changing the schedule

The cron line in `.github/workflows/daily-digest.yml` is in UTC. `30 11 * * *`
is 7:30 AM US Eastern during daylight saving; it drifts to 6:30 AM ET during
standard time since GitHub Actions cron doesn't follow daylight saving. If
that hour matters to you, just nudge the cron by one hour when clocks change,
or trigger runs manually anytime from the Actions tab regardless of schedule.

## Adjusting scope or topics later

Edit `TOPIC_QUERIES` in `scripts/fetch_pubmed.py` to add/remove search terms,
and edit `MASTER_PROMPT.md` to change triage rules, categories, or tone —
both take effect on the very next run, no redeploy needed beyond the commit.
