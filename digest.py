"""Monthly arXiv reading shortlist. Python 3.11+, standard library only."""
import argparse
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

NS = {"a": "http://www.w3.org/2005/Atom", "o": "http://a9.com/-/spec/opensearch/1.1/"}
ROOT = Path(__file__).resolve().parent


def month_bounds(month=None):
    if month:
        start = dt.datetime.strptime(month, "%Y-%m").date().replace(day=1)
    else:
        start = (dt.datetime.now(dt.timezone.utc).date().replace(day=1) - dt.timedelta(days=1)).replace(day=1)
    end = (start.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return start, end


def request(url, data=None, token=None):
    headers = {"User-Agent": "ai-research-digest/1.0"}
    if token:
        headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=headers)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
        time.sleep(5 * 2 ** attempt)


def parse_feed(data):
    root = ET.fromstring(data)
    papers = []
    for entry in root.findall("a:entry", NS):
        url = entry.findtext("a:id", "", NS)
        if "/abs/" not in url:
            raise ValueError("arXiv returned an error entry: " + entry.findtext("a:summary", "", NS))
        clean = lambda tag: " ".join(entry.findtext("a:" + tag, "", NS).split())
        papers.append({"id": re.sub(r"v\d+$", "", url.split("/abs/")[1]),
                       "title": clean("title"), "abstract": clean("summary"),
                       "published": clean("published"),
                       "authors": [a.findtext("a:name", "", NS) for a in entry.findall("a:author", NS)],
                       "categories": [c.attrib["term"] for c in entry.findall("a:category", NS)]})
    return papers, int(root.findtext("o:totalResults", "0", NS))


def fetch(config, start, end):
    last = end - dt.timedelta(days=1)
    query = "(" + " OR ".join("cat:" + c for c in config["categories"]) + ")"
    query += f" AND submittedDate:[{start:%Y%m%d}0000 TO {last:%Y%m%d}2359]"
    found, offset, total = {}, 0, None
    cap = config["max_candidates"]
    if not 10 <= cap <= 30000:
        raise ValueError("max_candidates must be between 10 and 30000")
    while offset < cap:
        size = min(500, cap - offset)
        params = urllib.parse.urlencode({"search_query": query, "start": offset, "max_results": size,
                                        "sortBy": "submittedDate", "sortOrder": "descending"})
        if offset:
            time.sleep(3.1)
        batch, total = parse_feed(request("https://export.arxiv.org/api/query?" + params))
        if not batch:
            if offset < total:
                raise RuntimeError("Unexpected empty arXiv page; refusing an incomplete digest")
            break
        for p in batch:
            if start.isoformat() <= p["published"][:10] < end.isoformat():
                found[p["id"]] = p
        offset += len(batch)
        if offset >= total:
            break
    return list(found.values()), total, query


def rank(papers, config):
    ranked = []
    for paper in papers:
        p = dict(paper)
        text = (p["title"] + " " + p["abstract"]).lower()
        p["signals"] = [term for term in config["weights"] if term.lower() in text]
        p["score"] = sum(config["weights"][term] for term in p["signals"])
        ranked.append(p)
    ranked.sort(key=lambda p: (-p["score"], p["id"]))
    # Greedy diversity: discount terms already represented in earlier selections.
    selected, seen = [], set()
    while ranked and len(selected) < config["top_n"]:
        best = max(ranked, key=lambda p: sum(config["weights"][t] * (0.5 if t in seen else 1) for t in p["signals"]))
        ranked.remove(best)
        selected.append(best)
        seen.update(best["signals"])
    return selected


def render(month, selected, count, total, query):
    lines = [f"# AI research digest — {month}", "",
             f"Selected {len(selected)} papers from {count} unique candidates; arXiv reported {total} matches.", "",
             "This is a configurable, abstract-based reading shortlist, not an expert assessment of the ten best papers. "
             "Scores use topic and practical-use keywords with a diversity discount. Claims below are author abstracts; "
             "full texts and results have not been independently verified. arXiv papers may be preprints.", ""]
    if total > count:
        lines += ["**Coverage note:** the candidate cap or filtering excluded some results; this shortlist does not cover the whole month.", ""]
    for i, p in enumerate(selected, 1):
        title = html.escape(p["title"]).replace("[", "&#91;").replace("]", "&#93;")
        lines += [f"## {i}. {title}", "",
                  f"[Paper](https://arxiv.org/abs/{p['id']}) · [PDF](https://arxiv.org/pdf/{p['id']})", "",
                  "Authors: " + html.escape(", ".join(p["authors"][:6])) + (" et al." if len(p["authors"]) > 6 else ""), "",
                  f"First submitted: {p['published'][:10]} · Categories: {', '.join(p['categories'])}", "",
                  f"Selection signals (score {p['score']}): " + (", ".join(p["signals"]) or "No configured keywords; diversity/fallback selection"), "",
                  "**Author abstract:** " + html.escape(p["abstract"]), ""]
    lines += ["## Search scope", "", "```text", query, "```", ""]
    return "\n".join(lines)


def publish_issue(month, body):
    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid GITHUB_REPOSITORY")
    base = f"https://api.github.com/repos/{repo}/issues"
    title = f"AI research digest — {month}"
    # Exact title lookup over all pages avoids duplicate issues on reruns.
    page = 1
    while True:
        issues = json.loads(request(f"{base}?state=all&per_page=100&page={page}", token=token))
        existing = next((i for i in issues if i["title"] == title and "pull_request" not in i), None)
        if existing:
            print("Already published:", existing["html_url"])
            return
        if len(issues) < 100:
            break
        page += 1
    if len(body.encode()) > 60000:
        raise ValueError("Digest too large for a GitHub issue; use the saved Markdown artifact")
    issue = json.loads(request(base, {"title": title, "body": body}, token))
    print("Published:", issue["html_url"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", help="YYYY-MM; defaults to previous complete UTC month")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "digests")
    parser.add_argument("--publish", action="store_true", help="Create a GitHub issue")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if not 1 <= config["top_n"] <= 50 or not config["categories"]:
        raise ValueError("Require 1–50 papers and at least one category")
    start, end = month_bounds(args.month)
    month = start.strftime("%Y-%m")
    papers, total, query = fetch(config, start, end)
    if len(papers) < config["top_n"]:
        raise RuntimeError(f"Only {len(papers)} candidates; refusing to publish fewer than {config['top_n']} papers")
    selected = rank(papers, config)
    body = render(month, selected, len(papers), total, query)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / f"{month}.md").write_text(body, encoding="utf-8")
    (args.output_dir / f"{month}.json").write_text(json.dumps({"month": month, "candidates": len(papers), "total_matches": total, "query": query, "papers": selected}, indent=2), encoding="utf-8")
    print(f"Saved {len(selected)} papers for {month} to {args.output_dir}")
    if args.publish:
        publish_issue(month, body)


if __name__ == "__main__":
    main()
