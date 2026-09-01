"""
Renders docs/index.html (today's digest) and docs/archive/<date>.html (one
full page per past day) from data/latest_digest.json and data/history.json.

This is a static rebuild -- all history lives in the committed JSON files,
not in browser storage, so it's correct for any visitor/device, and every
past day's full write-up (not just a title) stays reviewable.
"""
import html
import json
import os

HERE = os.path.dirname(__file__)

CATEGORY_LABEL = {
    "practice-changing": "Practice-changing",
    "notable": "Notable",
    "preliminary": "Preliminary",
}


def load(path):
    with open(os.path.join(HERE, "..", "data", path)) as f:
        return json.load(f)


def render_item(item):
    cat = item.get("category", "notable")
    label = CATEGORY_LABEL.get(cat, cat.title())
    caveat_html = ""
    if item.get("caveat"):
        caveat_html = f'<div class="caveat"><b>Caveat:</b> {html.escape(item["caveat"])}</div>'
    cite_bits = [f'PMID {html.escape(item["pmid"])}']
    if item.get("doi"):
        cite_bits.append(
            f'<a href="https://doi.org/{html.escape(item["doi"])}" target="_blank" '
            f'rel="noopener">doi.org/{html.escape(item["doi"])}</a>'
        )
    journal_year = " &middot; ".join(
        x for x in [html.escape(item.get("journal", "")), html.escape(str(item.get("year", "")))] if x
    )

    return f"""
    <div class="entry {cat}" data-pmid="{html.escape(item['pmid'])}">
      <div class="entry-head">
        <h2 class="entry-title">{html.escape(item['title'])}</h2>
        <span class="badge {cat}">{html.escape(label)}</span>
      </div>
      {f'<div class="journal-line">{journal_year}</div>' if journal_year else ''}
      <p>{html.escape(item['summary'])}</p>
      {caveat_html}
      <div class="cite">{' &middot; '.join(cite_bits)}</div>
      <div class="quiz">
        <div class="quiz-q"><b>Case:</b> {html.escape(item['quiz_question'])}</div>
        <button class="btn" onclick="reveal(this)">Reveal</button>
        <div class="reveal">{html.escape(item['quiz_answer'])}</div>
      </div>
    </div>
    """


def render_refresher(topic):
    return f"""
    <div class="entry refresher">
      <div class="entry-head">
        <h2 class="entry-title">Refresher: {html.escape(topic)}</h2>
        <span class="badge refresher">Spaced repetition</span>
      </div>
      <p>No new candidate this run cleared the practice-changing or notable
      bar honestly, so this day was a fundamentals refresher instead of
      manufactured novelty.</p>
    </div>
    """


def session_items_html(session):
    if session.get("items"):
        return "\n".join(render_item(i) for i in session["items"])
    if session.get("refresher_needed"):
        return render_refresher(session.get("refresher_topic", "core concept"))
    return '<div class="empty-hist">Nothing recorded for this day.</div>'


def render_history_panel(sessions, current_date, asset_prefix="archive/"):
    past = [s for s in reversed(sessions) if s["date"] != current_date]
    if not past:
        return '<div class="empty-hist">No past sessions yet.</div>'
    rows = []
    for s in past:
        if s.get("refresher_needed") and not s.get("items"):
            label = f'Refresher: {html.escape(s.get("refresher_topic",""))}'
        else:
            n = len(s.get("items", []))
            label = f'{n} paper{"s" if n != 1 else ""} reviewed'
        rows.append(
            f'<a class="hist-item" href="{asset_prefix}{html.escape(s["date"])}.html">'
            f'<span class="hist-title">{label}</span>'
            f'<span class="hist-date">{html.escape(s["date"])}</span></a>'
        )
    return "\n".join(rows)


def build_page(date_label, items_html, session_count, total_papers, history_html,
                css_href="assets/style.css", back_link=""):
    return TEMPLATE.format(
        date=html.escape(date_label),
        session_count=session_count,
        total_papers=total_papers,
        items_html=items_html,
        history_html=history_html,
        css_href=css_href,
        back_link=back_link,
    )


def main():
    digest = load("latest_digest.json")
    history = load("history.json")

    sessions = history.get("sessions", [])
    total_papers = len(history.get("used_pmids", []))
    session_count = len(sessions)

    # --- Today's page (docs/index.html) ---
    if digest.get("items"):
        items_html = "\n".join(render_item(i) for i in digest["items"])
    elif digest.get("refresher_needed"):
        items_html = render_refresher(digest.get("refresher_topic", "core concept"))
    else:
        items_html = '<div class="empty-hist">Nothing to show.</div>'

    history_html = render_history_panel(sessions, digest["date"], asset_prefix="archive/")

    page = build_page(
        date_label=digest["date"],
        items_html=items_html,
        session_count=session_count,
        total_papers=total_papers,
        history_html=history_html,
        css_href="assets/style.css",
        back_link="",
    )

    docs_dir = os.path.join(HERE, "..", "docs")
    archive_dir = os.path.join(docs_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)

    with open(os.path.join(docs_dir, "index.html"), "w") as f:
        f.write(page)

    # --- One full archive page per past day, so history is actually reviewable ---
    for s in sessions:
        s_items_html = session_items_html(s)
        # Archive pages link back to "today" and list all OTHER days in their
        # own history panel too, so you can hop between any two days directly.
        s_history_html = render_history_panel(sessions, s["date"], asset_prefix="")
        archive_page = build_page(
            date_label=s["date"],
            items_html=s_items_html,
            session_count=session_count,
            total_papers=total_papers,
            history_html=s_history_html,
            css_href="../assets/style.css",
            back_link='<a class="back-link" href="../index.html">&larr; Back to today</a>',
        )
        with open(os.path.join(archive_dir, f'{s["date"]}.html'), "w") as f:
            f.write(archive_page)

    print(f"Rendered docs/index.html and {len(sessions)} archive page(s).")


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pituitary &amp; Adrenal CME &mdash; {date}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,500;0,8..60,600;1,8..60,400&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{css_href}">
</head>
<body>
<div class="wrap">
  {back_link}
  <div class="masthead">
    <div>
      <h1>Pituitary &amp; Adrenal CME</h1>
      <div class="sub">Auto-updating daily &middot; pituitary &amp; adrenal neuroendocrinology only</div>
    </div>
    <div class="stats">
      <div>Session <b>#{session_count}</b></div>
      <div><b>{total_papers}</b> papers reviewed</div>
    </div>
  </div>
  <div class="today-label">{date}</div>
  <div id="digest">
    {items_html}
  </div>
  <div class="disclaimer">
    AI-curated from PubMed abstracts on an automated daily schedule; verify primary sources before altering practice.
  </div>
  <button class="history-toggle" onclick="document.getElementById('historyPanel').classList.toggle('shown'); this.textContent = this.textContent.includes('View') ? 'Hide past sessions ↑' : 'View past sessions ↓';">View other sessions &darr;</button>
  <div id="historyPanel">
    {history_html}
  </div>
  <footer>
    Sources verified via PubMed at generation time. Rebuilt automatically once daily.
    Scope: pituitary &amp; adrenal neuroendocrinology only.
  </footer>
</div>
<script>
function reveal(btn){{
  btn.nextElementSibling.classList.add('shown');
}}
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
