"""
Takes data/candidates.json (real PubMed records with real abstracts) and asks
Claude, via the Anthropic API, to triage and summarize them according to
MASTER_PROMPT.md. The model is instructed to work ONLY from the provided
abstract text and to never fabricate a finding or citation.

Requires the ANTHROPIC_API_KEY environment variable (set as a GitHub Actions
secret -- never commit this key to the repo).
"""
import json
import os
import re
from datetime import date

import anthropic

MODEL = "claude-sonnet-4-6"
HERE = os.path.dirname(__file__)


def load_master_prompt():
    with open(os.path.join(HERE, "..", "MASTER_PROMPT.md")) as f:
        return f.read()


def load_candidates():
    with open(os.path.join(HERE, "..", "data", "candidates.json")) as f:
        return json.load(f)


def load_history():
    path = os.path.join(HERE, "..", "data", "history.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"used_pmids": [], "sessions": []}


def save_history(history):
    path = os.path.join(HERE, "..", "data", "history.json")
    with open(path, "w") as f:
        json.dump(history, f, indent=2)


def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY environment variable is required.")

    master_prompt = load_master_prompt()
    candidate_data = load_candidates()
    history = load_history()

    candidates = candidate_data.get("candidates", [])
    if not candidates:
        # Genuinely nothing new -- be honest about it, same as the rule requires.
        result = {
            "date": date.today().isoformat(),
            "items": [],
            "refresher_needed": True,
            "refresher_topic": "core pituitary/adrenal physiology (no new candidates retrieved this run)",
        }
    else:
        client = anthropic.Anthropic(api_key=api_key)
        user_payload = {
            "already_covered_pmids": candidate_data.get("already_covered_pmids", []),
            "candidates": candidates,
        }
        message = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            system=master_prompt,
            messages=[{
                "role": "user",
                "content": (
                    "Here are today's real candidate PubMed records (with real "
                    "abstracts). Select and summarize per your instructions, "
                    "returning ONLY the JSON object specified.\n\n"
                    + json.dumps(user_payload, indent=2)
                ),
            }],
        )
        raw_text = "".join(
            block.text for block in message.content if block.type == "text"
        )
        try:
            result = extract_json(raw_text)
        except Exception as e:
            raise SystemExit(f"Failed to parse model output as JSON: {e}\n\nRaw output:\n{raw_text}")

    # Cross-check: never trust category/citation fields blindly -- verify each
    # selected item's pmid/doi actually appears in the real candidate list
    # before it's allowed into the site. This is a hard guard against
    # fabrication slipping through.
    candidates_by_pmid = {c["pmid"]: c for c in candidates}
    verified_items = []
    for item in result.get("items", []):
        real = candidates_by_pmid.get(item.get("pmid"))
        if not real:
            print(f"DROPPED item with unverifiable pmid {item.get('pmid')} -- "
                  f"not present in fetched candidate list.")
            continue
        if real.get("doi") and item.get("doi") != real.get("doi"):
            item["doi"] = real["doi"]  # correct rather than trust the model's copy
        item["title"] = real["title"]  # always use the verified real title
        item["journal"] = real.get("journal", "")
        item["year"] = real.get("year", "")
        verified_items.append(item)

    result["items"] = verified_items
    if not verified_items and not result.get("refresher_needed"):
        result["refresher_needed"] = True
        result.setdefault("refresher_topic", "core pituitary/adrenal physiology")

    # Update history: record used PMIDs (never re-shown) and this session's summary.
    used_pmids = set(history.get("used_pmids", []))
    used_pmids.update(item["pmid"] for item in verified_items)
    history["used_pmids"] = sorted(used_pmids)
    history.setdefault("sessions", []).append({
        "date": result["date"],
        # Store full item content (not just title/category) so any past
        # day's full digest -- summary, caveat, quiz -- can be rebuilt and
        # reviewed later, not just listed by title.
        "items": verified_items,
        "refresher_needed": result.get("refresher_needed", False),
        "refresher_topic": result.get("refresher_topic", ""),
    })
    save_history(history)

    out_path = os.path.join(HERE, "..", "data", "latest_digest.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Digest built: {len(verified_items)} verified items, "
          f"refresher_needed={result.get('refresher_needed')}")


if __name__ == "__main__":
    main()
