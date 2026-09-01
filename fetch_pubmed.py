"""
Fetches candidate PubMed articles for the pituitary/adrenal CME digest.

Uses NCBI E-utilities directly (no API key required, but a free NCBI API key
is recommended to raise the rate limit from 3/sec to 10/sec -- see README).

Output: writes data/candidates.json, a list of real, verified PubMed records
(pmid, doi, title, abstract, journal, pub_date) for the digest-writing step
to select from. This script does NOT judge clinical relevance -- that
happens in build_digest.py using the actual Anthropic API, grounded only in
what this script retrieves.
"""
import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")  # optional, raises rate limit
SLEEP = 0.11 if NCBI_API_KEY else 0.35  # stay under rate limits

# Search topics scoped strictly to pituitary + adrenal neuroendocrinology.
# Each is ANDed with a 10-year publication-date window at request time.
TOPIC_QUERIES = [
    "pituitary adenoma AND (guideline OR randomized controlled trial OR cohort)",
    "hypopituitarism treatment",
    "Cushing's syndrome AND (guideline OR randomized controlled trial)",
    "Cushing's disease treatment",
    "adrenal insufficiency management",
    "adrenal incidentaloma",
    "pheochromocytoma management",
    "primary aldosteronism screening OR treatment",
    "acromegaly treatment",
    "prolactinoma management",
]

RESULTS_PER_TOPIC = 8
YEARS_BACK = 10


def esearch(query, date_from, date_to):
    params = {
        "db": "pubmed",
        "term": query,
        "datetype": "pdat",
        "mindate": date_from,
        "maxdate": date_to,
        "retmax": RESULTS_PER_TOPIC,
        "sort": "most+recent",
        "retmode": "json",
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    url = f"{EUTILS}/esearch.fcgi?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read().decode())
    return data.get("esearchresult", {}).get("idlist", [])


def efetch(pmids):
    if not pmids:
        return []
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "abstract",
        "retmode": "xml",
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    url = f"{EUTILS}/efetch.fcgi?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        xml_bytes = r.read()
    return parse_pubmed_xml(xml_bytes)


def parse_pubmed_xml(xml_bytes):
    root = ET.fromstring(xml_bytes)
    records = []
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        pmid = pmid_el.text if pmid_el is not None else None
        if not pmid:
            continue

        title_el = article.find(".//ArticleTitle")
        title = "".join(title_el.itertext()).strip() if title_el is not None else ""

        abstract_parts = article.findall(".//AbstractText")
        abstract = " ".join("".join(p.itertext()).strip() for p in abstract_parts).strip()
        if not abstract:
            continue  # skip records with no abstract; can't ground a summary safely

        journal_el = article.find(".//Journal/Title")
        journal = journal_el.text if journal_el is not None else ""

        year_el = article.find(".//JournalIssue/PubDate/Year")
        medline_date_el = article.find(".//JournalIssue/PubDate/MedlineDate")
        year = year_el.text if year_el is not None else (
            medline_date_el.text[:4] if medline_date_el is not None else ""
        )

        doi = ""
        for eid in article.findall(".//ELocationID"):
            if eid.get("EIdType") == "doi":
                doi = eid.text
                break
        if not doi:
            for aid in article.findall(".//ArticleId"):
                if aid.get("IdType") == "doi":
                    doi = aid.text
                    break

        pub_types = [pt.text for pt in article.findall(".//PublicationType")]

        records.append({
            "pmid": pmid,
            "doi": doi,
            "title": title,
            "abstract": abstract,
            "journal": journal,
            "year": year,
            "publication_types": pub_types,
        })
    return records


def load_history():
    hist_path = os.path.join(os.path.dirname(__file__), "..", "data", "history.json")
    if os.path.exists(hist_path):
        with open(hist_path) as f:
            return json.load(f)
    return {"used_pmids": [], "sessions": []}


def main():
    history = load_history()
    already_covered = set(history.get("used_pmids", []))

    today = date.today()
    date_from = (today - timedelta(days=365 * YEARS_BACK)).strftime("%Y/%m/%d")
    date_to = today.strftime("%Y/%m/%d")

    all_pmids = set()
    for query in TOPIC_QUERIES:
        try:
            ids = esearch(query, date_from, date_to)
        except Exception as e:
            print(f"esearch failed for '{query}': {e}")
            ids = []
        all_pmids.update(ids)
        time.sleep(SLEEP)

    # Drop anything we've already used so the model can't re-select it,
    # and so we don't even spend tokens showing it duplicate content.
    new_pmids = [p for p in all_pmids if p not in already_covered]

    candidates = []
    batch_size = 40
    pmid_list = list(new_pmids)
    for i in range(0, len(pmid_list), batch_size):
        batch = pmid_list[i:i + batch_size]
        try:
            records = efetch(batch)
            candidates.extend(records)
        except Exception as e:
            print(f"efetch failed for batch starting {batch[0] if batch else '?'}: {e}")
        time.sleep(SLEEP)

    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "candidates.json")
    with open(out_path, "w") as f:
        json.dump({
            "fetched_at": today.isoformat(),
            "date_window": {"from": date_from, "to": date_to},
            "already_covered_pmids": sorted(already_covered),
            "candidates": candidates,
        }, f, indent=2)

    print(f"Fetched {len(candidates)} new candidate articles (with abstracts) "
          f"out of {len(new_pmids)} new PMIDs found; "
          f"{len(already_covered)} PMIDs already covered were excluded from search targets.")


if __name__ == "__main__":
    main()
