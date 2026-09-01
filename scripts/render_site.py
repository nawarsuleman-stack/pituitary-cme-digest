"""
Renders docs/index.html from data/latest_digest.json and data/history.json.
This is a static rebuild -- all history lives in the committed JSON files,
not in browser storage, so the page is correct for any visitor/device.
"""
import html
import json
import os

HERE = os.path.dirname(__file__)


def load(path):
    with open(os.path.join(HERE, "..", "data", path)) as f:
        return json.load(f)


CATEGORY_LABEL = {
    "practice-changing": "Practice-changing",
    "notable": "Notable",
    "preliminary": "Preliminary",
}


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
      bar honestly, so today is a fundamentals refresher instead of
      manufactured novelty.</p>
    </div>
    """


def render_history_panel(sessions, current_date):
    past = [s for s in reversed(sessions) if s["date"] != current_date]
    if not past:
        return '<div class="empty-hist">No past sessions yet.</div>'
    rows = []
    for s in past:
        if s.get("refresher_needed") and not s.get("items"):
            rows.append(
                f'<div class="hist-item"><span class="hist-title">Refresher: '
                f'{html.escape(s.get("refresher_topic",""))}</span>'
                f'<span class="hist-date">{html.escape(s["date"])}</span></div>'
            )
        for it in s.get("items", []):
            rows.append(
                f'<div class="hist-item"><span class="hist-title">{html.escape(it["title"])}</span>'
                f'<span class="hist-date">{html.escape(s["date"])}</span></div>'
            )
    return "\n".join(rows)


def main():
    digest = load("latest_digest.json")
    history = load("history.json")

    if digest.get("items"):
        items_html = "\n".join(render_item(i) for i in digest["items"])
    elif digest.get("refresher_needed"):
        items_html = render_refresher(digest.get("refresher_topic", "core concept"))
    else:
        items_html = '<div class="empty-hist">Nothing to show.</div>'

    total_papers = len(history.get("used_pmids", []))
    session_count = len(history.get("sessions", []))
    history_html = render_history_panel(history.get("sessions", []), digest["date"])

    page = TEMPLATE.format(
        date=html.escape(digest["date"]),
        session_count=session_count,
        total_papers=total_papers,
        items_html=items_html,
        history_html=history_html,
    )

    docs_dir = os.path.join(HERE, "..", "docs")
    os.makedirs(docs_dir, exist_ok=True)
    with open(os.path.join(docs_dir, "index.html"), "w") as f:
        f.write(page)

    print("Rendered docs/index.html")


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pituitary &amp; Adrenal CME</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,500;0,8..60,600;1,8..60,400&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<div class="wrap">
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
  <button class="history-toggle" onclick="document.getElementById('historyPanel').classList.toggle('shown'); this.textContent = this.textContent.includes('View') ? 'Hide past sessions ↑' : 'View past sessions ↓';">View past sessions &darr;</button>
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
