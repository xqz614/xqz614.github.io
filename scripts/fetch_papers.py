#!/usr/bin/env python3
"""
Daily Paper Fetcher (v3 - Fetch Only, No LLM Analysis)
Fetches papers from arXiv, bioRxiv, and OpenAlex.
AI analysis is handled on-demand via the frontend.
"""

import json
import time
import hashlib
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

# ============ Configuration ============

RESEARCH_DIRECTIONS = {
    "medical": {
        "name": "Medical Dialogue & NLP",
        "arxiv_queries": [
            'cat:cs.CL AND (abs:"medical dialogue" OR abs:"clinical dialogue" OR abs:"healthcare conversation")',
            'cat:cs.CL AND (abs:"medical NLP" OR abs:"clinical NLP" OR abs:"biomedical NLP")',
        ],
        "openalex_queries": [
            "medical dialogue system clinical conversation AI",
            "biomedical NLP clinical text mining large language model",
        ],
        "openalex_concepts": "artificial intelligence,natural language processing,medicine",
        "biorxiv_keywords": ["medical dialogue", "clinical NLP", "medical AI"],
    },
    "cell": {
        "name": "Virtual Cell",
        "arxiv_queries": [
            'cat:q-bio.QM AND (abs:"virtual cell" OR abs:"cell simulation" OR abs:"perturbation prediction")',
            'cat:cs.LG AND abs:"single cell" AND (abs:"foundation model" OR abs:"gene expression")',
        ],
        "openalex_queries": [
            "virtual cell simulation computational biology AI",
            "single cell foundation model perturbation prediction",
        ],
        "openalex_concepts": "artificial intelligence,computational biology,cell biology",
        "biorxiv_keywords": ["virtual cell", "single cell foundation", "perturbation prediction"],
    },
    "llm": {
        "name": "LLM & NLP Frontiers",
        "arxiv_queries": [
            'cat:cs.CL AND (abs:"large language model" OR abs:"LLM") AND (abs:"reasoning" OR abs:"alignment")',
            'cat:cs.CL AND abs:"reinforcement learning" AND abs:"language model"',
        ],
        "openalex_queries": [
            "large language model reasoning reinforcement learning 2025",
            "multimodal foundation model vision language 2025",
        ],
        "openalex_concepts": "artificial intelligence,natural language processing,deep learning",
        "biorxiv_keywords": [],
    },
}

MAX_PAPERS_PER_DIRECTION = 10
MAX_TOTAL_PAPERS = 1000
RETENTION_DAYS = 180  # Keep papers for 6 months


# ============ HTTP Helper ============

def http_get(url, max_retries=2, timeout=20):
    """HTTP GET with fast-fail retry."""
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "PaperTracker/1.0 (mailto:zhixiaoquan@tju.edu.cn)"
            })
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 5 * (attempt + 1)
                print(f"    [429] Rate limited, wait {wait}s ({attempt+1}/{max_retries})")
                time.sleep(wait)
            else:
                print(f"    [HTTP {e.code}] {e.reason}")
                return None
        except Exception as e:
            print(f"    [ERR] {str(e)[:60]} ({attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2)
    return None


# ============ arXiv Fetcher ============

def fetch_arxiv(query, max_results=5):
    papers = []
    try:
        params = urllib.parse.urlencode({
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        })
        url = f"http://export.arxiv.org/api/query?{params}"
        data = http_get(url, timeout=30)
        if not data:
            return papers

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(data)

        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            abstract_el = entry.find("atom:summary", ns)
            published_el = entry.find("atom:published", ns)
            id_el = entry.find("atom:id", ns)

            if not all(el is not None for el in [title_el, abstract_el, published_el, id_el]):
                continue

            title = " ".join(title_el.text.strip().split())
            abstract = " ".join(abstract_el.text.strip().split())
            published = published_el.text[:10]
            arxiv_id = id_el.text.split("/abs/")[-1]

            authors = []
            for author in entry.findall("atom:author", ns):
                name_el = author.find("atom:name", ns)
                if name_el is not None:
                    authors.append(name_el.text)

            papers.append({
                "title": title,
                "authors": ", ".join(authors[:5]) + ("..." if len(authors) > 5 else ""),
                "abstract": abstract,
                "date": published,
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
                "source": "arxiv",
                "venue": "arXiv",
            })
    except Exception as e:
        print(f"  [WARN] arXiv error: {str(e)[:60]}")
    return papers


# ============ OpenAlex Fetcher ============

def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return ""
    words = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[k] for k in sorted(words.keys()))


def fetch_openalex(query, max_results=5):
    papers = []
    try:
        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        # Add relevance filter: only CS/AI/Bio related
        filter_str = f"from_publication_date:{cutoff},type:article"
        params = urllib.parse.urlencode({
            "search": query,
            "filter": filter_str,
            "sort": "publication_date:desc",
            "per_page": max_results,
            "mailto": "zhixiaoquan@tju.edu.cn",
            "select": "id,title,authorships,abstract_inverted_index,publication_date,primary_location,doi",
        })
        url = f"https://api.openalex.org/works?{params}"
        data = http_get(url, timeout=20)
        if not data:
            return papers

        result = json.loads(data)

        # Two-layer relevance filter: must have AI/CS method AND domain relevance
        ai_keywords = [
            "machine learning", "deep learning", "neural network", "nlp",
            "language model", "transformer", "bert", "gpt", "llm",
            "artificial intelligence", "reinforcement learning", "attention mechanism",
            "embedding", "pretrain", "pre-train", "fine-tun", "foundation model",
            "multimodal", "generative", "diffusion", "autoencoder", "contrastive",
            "graph neural", "representation learning", "self-supervised",
        ]
        domain_keywords = [
            "medical", "clinical", "biomedical", "healthcare", "diagnosis",
            "patient", "disease", "drug", "treatment", "radiology", "pathology",
            "cell", "gene", "genomic", "transcriptom", "protein", "perturbation",
            "single-cell", "single cell", "scRNA", "omics", "biological",
            "dialogue", "conversation", "reasoning", "alignment", "agent",
            "benchmark", "evaluation", "text", "summariz", "extract",
        ]

        for item in result.get("results", []):
            abstract = reconstruct_abstract(item.get("abstract_inverted_index"))
            if not abstract or len(abstract) < 50:
                continue

            title = item.get("title", "")
            if not title:
                continue

            # Check relevance: must match at least one AI keyword AND one domain keyword
            combined = (title + " " + abstract).lower()
            has_ai = any(kw in combined for kw in ai_keywords)
            has_domain = any(kw in combined for kw in domain_keywords)
            if not (has_ai and has_domain):
                continue

            authorships = item.get("authorships", []) or []
            authors = [a.get("author", {}).get("display_name", "") for a in authorships[:5]]
            if len(authorships) > 5:
                authors.append("...")
            authors_str = ", ".join(a for a in authors if a)

            loc = item.get("primary_location", {}) or {}
            src = loc.get("source", {}) or {}
            venue = src.get("display_name", "")

            source = "journal"
            if venue:
                vl = venue.lower()
                if "arxiv" in vl:
                    source = "arxiv"
                elif "biorxiv" in vl or "medrxiv" in vl:
                    source = "biorxiv"
                elif any(c in vl for c in ["conference", "proceedings", "workshop",
                         "acl", "emnlp", "naacl", "neurips", "icml", "iclr", "aaai"]):
                    source = "conference"

            doi = item.get("doi", "")
            paper_url = doi if doi else ""
            # Skip papers without real URLs (openalex internal links are useless)
            if not paper_url:
                continue

            papers.append({
                "title": title,
                "authors": authors_str,
                "abstract": abstract,
                "date": item.get("publication_date", ""),
                "url": paper_url,
                "pdf_url": "",
                "source": source,
                "venue": venue,
            })
    except Exception as e:
        print(f"  [WARN] OpenAlex error: {str(e)[:60]}")
    return papers


# ============ bioRxiv Fetcher ============

def fetch_biorxiv(keywords, max_results=3):
    papers = []
    if not keywords:
        return papers
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        url = f"https://api.biorxiv.org/details/biorxiv/{start}/{end}/0/30"
        data = http_get(url, timeout=30)
        if not data:
            return papers

        result = json.loads(data)
        for item in result.get("collection", []):
            title = item.get("title", "")
            abstract = item.get("abstract", "")
            combined = (title + " " + abstract).lower()

            if any(kw.lower() in combined for kw in keywords):
                doi = item.get("doi", "")
                papers.append({
                    "title": title,
                    "authors": item.get("authors", ""),
                    "abstract": abstract,
                    "date": item.get("date", ""),
                    "url": f"https://doi.org/{doi}" if doi else "",
                    "pdf_url": "",
                    "source": "biorxiv",
                    "venue": "bioRxiv",
                })
                if len(papers) >= max_results:
                    break
    except Exception as e:
        print(f"  [WARN] bioRxiv error: {str(e)[:60]}")
    return papers


# ============ Utilities ============

def deduplicate(papers):
    seen = set()
    unique = []
    for p in papers:
        key = re.sub(r'[^a-z0-9]', '', p["title"].lower())[:80]
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def paper_id(paper):
    raw = f"{paper['title']}_{paper.get('date', '')}".encode()
    return hashlib.md5(raw).hexdigest()[:12]


def load_existing(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "papers" in data:
                return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {"last_updated": "", "papers": []}


# ============ Main ============

def main():
    t0 = time.time()
    print("=" * 60)
    print("Paper Tracker - Daily Fetch (v3 - No LLM)")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    data_file = project_dir / "papers" / "papers_data.json"
    data_file.parent.mkdir(parents=True, exist_ok=True)

    existing = load_existing(data_file)
    existing_ids = {p.get("id", "") for p in existing["papers"]}

    all_new = []

    for direction, config in RESEARCH_DIRECTIONS.items():
        print(f"\n--- {config['name']} ---")
        direction_papers = []

        # 1. arXiv
        for q in config["arxiv_queries"]:
            print(f"  [arXiv] {q[:55]}...")
            papers = fetch_arxiv(q, max_results=5)
            print(f"    -> {len(papers)} papers")
            direction_papers.extend(papers)
            time.sleep(3)

        # 2. OpenAlex
        for q in config.get("openalex_queries", []):
            print(f"  [OpenAlex] {q[:55]}...")
            papers = fetch_openalex(q, max_results=5)
            print(f"    -> {len(papers)} papers")
            direction_papers.extend(papers)
            time.sleep(1)

        # 3. bioRxiv
        keywords = config.get("biorxiv_keywords", [])
        if keywords:
            print(f"  [bioRxiv] keywords: {', '.join(keywords[:3])}")
            papers = fetch_biorxiv(keywords, max_results=3)
            print(f"    -> {len(papers)} papers")
            direction_papers.extend(papers)

        # Deduplicate & tag
        direction_papers = deduplicate(direction_papers)
        for p in direction_papers:
            p["direction"] = direction
            p["id"] = paper_id(p)

        # Filter existing
        new_papers = [p for p in direction_papers if p["id"] not in existing_ids]
        new_papers.sort(key=lambda x: x.get("date", ""), reverse=True)
        new_papers = new_papers[:MAX_PAPERS_PER_DIRECTION]

        print(f"  Total: {len(direction_papers)}, New: {len(new_papers)}")
        all_new.extend(new_papers)

    # Merge & save
    all_papers = all_new + existing["papers"]
    today = datetime.now().strftime("%Y-%m-%d")
    cutoff = (datetime.now() - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    # Filter: remove future dates and papers older than retention period
    all_papers = [p for p in all_papers if cutoff <= p.get("date", "9999") <= today]
    # Remove papers with openalex internal URLs (no real link)
    all_papers = [p for p in all_papers if not p.get("url", "").startswith("https://openalex.org/")]
    all_papers.sort(key=lambda x: x.get("date", ""), reverse=True)
    all_papers = all_papers[:MAX_TOTAL_PAPERS]

    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "papers": all_papers,
    }
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    elapsed = int(time.time() - t0)
    print(f"\n{'=' * 60}")
    print(f"Done in {elapsed}s ({elapsed // 60}m {elapsed % 60}s)")
    print(f"Papers: {len(all_papers)}, New: {len(all_new)}")
    print(f"Saved: {data_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
