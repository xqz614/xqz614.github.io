#!/usr/bin/env python3
"""
Daily Paper Fetcher & AI Analyzer
Fetches papers from arXiv, bioRxiv, and OpenAlex,
then generates deep analysis using ModelScope Qwen API.
"""

import os
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

MODELSCOPE_API_KEY = os.environ.get("MODELSCOPE_API_KEY", "")
MODELSCOPE_BASE_URL = "https://api-inference.modelscope.cn/v1/"
MODELSCOPE_MODEL = "Qwen/Qwen3-235B-A22B"

RESEARCH_DIRECTIONS = {
    "medical": {
        "name": "Medical Dialogue & NLP",
        "arxiv_queries": [
            'cat:cs.CL AND (abs:"medical dialogue" OR abs:"clinical dialogue" OR abs:"healthcare conversation")',
            'cat:cs.CL AND (abs:"medical NLP" OR abs:"clinical NLP" OR abs:"biomedical NLP")',
            'cat:cs.AI AND (abs:"medical agent" OR abs:"clinical agent")',
        ],
        "openalex_queries": [
            "medical dialogue system large language model",
            "clinical NLP biomedical text mining",
            "medical question answering healthcare AI",
        ],
        "biorxiv_keywords": ["medical dialogue", "clinical NLP", "medical AI"],
    },
    "cell": {
        "name": "Virtual Cell",
        "arxiv_queries": [
            'cat:q-bio.QM AND (abs:"virtual cell" OR abs:"cell simulation" OR abs:"perturbation prediction")',
            'cat:q-bio.GN AND (abs:"single cell" AND abs:"foundation model")',
            'cat:cs.LG AND abs:"single cell" AND abs:"gene expression"',
        ],
        "openalex_queries": [
            "virtual cell model single cell foundation model",
            "perturbation prediction gene expression deep learning",
            "single cell genomics transformer model",
        ],
        "biorxiv_keywords": ["virtual cell", "single cell foundation", "perturbation prediction"],
    },
    "llm": {
        "name": "LLM & NLP Frontiers",
        "arxiv_queries": [
            'cat:cs.CL AND (abs:"large language model" OR abs:"LLM") AND (abs:"reasoning" OR abs:"alignment")',
            'cat:cs.CL AND abs:"reinforcement learning" AND abs:"language model"',
            'cat:cs.AI AND abs:"multimodal" AND abs:"foundation model"',
            'cat:cs.CL AND (abs:"retrieval augmented" OR abs:"RAG" OR abs:"in-context learning")',
        ],
        "openalex_queries": [
            "large language model reasoning reinforcement learning",
            "LLM agent tool use planning",
            "multimodal foundation model vision language",
        ],
        "biorxiv_keywords": [],
    },
}

MAX_PAPERS_PER_DIRECTION = 15
MAX_ANALYSIS_PER_RUN = 30


# ============ HTTP Helper ============

def http_get(url, max_retries=2, timeout=30):
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
                wait = 10 * (attempt + 1)
                print(f"    [429] Rate limited, wait {wait}s ({attempt+1}/{max_retries})")
                time.sleep(wait)
            else:
                print(f"    [HTTP {e.code}] {e.reason}")
                return None
        except Exception as e:
            print(f"    [ERR] {str(e)[:80]} ({attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(3)
    return None


# ============ arXiv Fetcher ============

def fetch_arxiv(query, max_results=8):
    """Fetch from arXiv API."""
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
        data = http_get(url, timeout=45)
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
        print(f"  [WARN] arXiv error: {str(e)[:80]}")
    return papers


# ============ OpenAlex Fetcher ============

def reconstruct_abstract(inverted_index):
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return ""
    words = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[k] for k in sorted(words.keys()))


def fetch_openalex(query, max_results=8):
    """Fetch from OpenAlex API (covers conferences, journals, preprints)."""
    papers = []
    try:
        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        params = urllib.parse.urlencode({
            "search": query,
            "filter": f"from_publication_date:{cutoff},type:article",
            "sort": "publication_date:desc",
            "per_page": max_results,
            "mailto": "zhixiaoquan@tju.edu.cn",
            "select": "id,title,authorships,abstract_inverted_index,publication_date,primary_location,doi,open_access",
        })
        url = f"https://api.openalex.org/works?{params}"
        data = http_get(url, timeout=30)
        if not data:
            return papers

        result = json.loads(data)

        for item in result.get("results", []):
            abstract = reconstruct_abstract(item.get("abstract_inverted_index"))
            if not abstract or len(abstract) < 50:
                continue

            title = item.get("title", "")
            if not title:
                continue

            # Authors
            authorships = item.get("authorships", []) or []
            authors = [a.get("author", {}).get("display_name", "") for a in authorships[:5]]
            if len(authorships) > 5:
                authors.append("...")
            authors_str = ", ".join(a for a in authors if a)

            # Venue
            loc = item.get("primary_location", {}) or {}
            src = loc.get("source", {}) or {}
            venue = src.get("display_name", "")

            # Determine source type
            source = "journal"
            if venue:
                venue_lower = venue.lower()
                if "arxiv" in venue_lower:
                    source = "arxiv"
                elif "biorxiv" in venue_lower or "medrxiv" in venue_lower:
                    source = "biorxiv"
                elif any(c in venue_lower for c in ["conference", "proceedings", "workshop", "symposium",
                         "acl", "emnlp", "naacl", "neurips", "icml", "iclr", "aaai", "ijcai", "coling"]):
                    source = "conference"

            # URL
            doi = item.get("doi", "")
            paper_url = doi if doi else item.get("id", "")

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
        print(f"  [WARN] OpenAlex error: {str(e)[:80]}")
    return papers


# ============ bioRxiv Fetcher ============

def fetch_biorxiv(keywords, max_results=5):
    """Fetch from bioRxiv API, filter by keywords."""
    papers = []
    if not keywords:
        return papers
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        url = f"https://api.biorxiv.org/details/biorxiv/{start}/{end}/0/50"
        data = http_get(url, timeout=45)
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
        print(f"  [WARN] bioRxiv error: {str(e)[:80]}")
    return papers


# ============ LLM Analysis ============

ANALYSIS_PROMPT = """你是一名AI领域的研究生，目标是深入理解论文的方法部分，包括方法动机、设计逻辑、流程细节、优势与不足，以便学习和在研究中借鉴。你的角色是高效、深入的论文分析师。

请根据以下论文信息，进行深度分析。注意：你只能基于提供的摘要和标题进行分析，如果信息不足以回答某个部分，请基于合理推断给出分析，并注明"基于摘要推断"。

论文标题：{title}
作者：{authors}
发表来源：{venue}
摘要：{abstract}

请按以下结构输出分析（使用中文）：

## 0. 摘要翻译
将摘要翻译为中文。

## 1. 方法动机
a) 作者为什么提出这个方法？阐述其背后的驱动力。
b) 现有方法的痛点/不足是什么？具体指出局限性。
c) 论文的研究假设或直觉是什么？用简洁语言概括。

## 2. 方法设计
a) 给出清晰的方法流程总结（pipeline），逐步解释输入→处理→输出。必须讲清楚每一步的具体操作和技术细节。
b) 如果涉及模型结构，描述每个模块的功能与作用，以及它们如何协同工作。
c) 如果有公式/算法，用通俗语言解释它们的意义和在方法中的角色。

## 3. 与其他方法对比
a) 本方法和现有主流方法相比，有什么本质不同？
b) 创新点在哪里？明确指出贡献度。
c) 在什么场景下更适用？分析其适用范围。
d) 用表格总结方法对比（优点/缺点/改进点）。

| 方法 | 优点 | 缺点 | 改进点 |
|------|------|------|--------|
| 本文方法 | ... | ... | ... |
| 对比方法1 | ... | ... | ... |
| 对比方法2 | ... | ... | ... |

## 4. 实验表现与优势
a) 作者如何验证该方法的有效性？
b) 实验结果的关键数据和结论。
c) 哪些场景下优势最明显？
d) 局限性分析。

## 5. 学习与应用
a) 论文是否开源？关键实现步骤是什么？
b) 需要注意的超参数、数据预处理、训练细节。
c) 该方法能否迁移到其他任务？

## 6. 总结
a) 用一句话概括这个方法的核心思想（不超过20字）。
b) 给出一个"速记版pipeline"（3-5个关键步骤），具有自明性，让读者只看pipeline即可大体理解论文内容。不要用比喻，直白讲出内容。"""


def call_llm(prompt, max_retries=2):
    """Call ModelScope Qwen API."""
    if not MODELSCOPE_API_KEY:
        return None

    url = f"{MODELSCOPE_BASE_URL}chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MODELSCOPE_API_KEY}",
    }
    payload = {
        "model": MODELSCOPE_MODEL,
        "messages": [
            {"role": "system", "content": "你是一名专业的AI论文分析师，擅长深入分析论文的方法、实验和创新点。请用中文回答。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 4000,
        "enable_thinking": False,
    }

    for attempt in range(max_retries):
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"]
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                usage = result.get("usage", {})
                print(f"    [LLM] tokens: {usage.get('total_tokens', '?')}")
                return content
        except Exception as e:
            print(f"    [LLM ERR] attempt {attempt+1}: {str(e)[:60]}")
            if attempt < max_retries - 1:
                time.sleep(5)
    return None


def parse_analysis(raw_text):
    """Parse LLM output into structured sections."""
    if not raw_text:
        return None

    analysis = {"raw": raw_text}
    sections = {
        "abstract_translation": r"## 0\. 摘要翻译\s*\n(.*?)(?=\n## |\Z)",
        "motivation": r"## 1\. 方法动机\s*\n(.*?)(?=\n## |\Z)",
        "method_design": r"## 2\. 方法设计\s*\n(.*?)(?=\n## |\Z)",
        "comparison": r"## 3\. 与其他方法对比\s*\n(.*?)(?=\n## |\Z)",
        "experiments": r"## 4\. 实验表现与优势\s*\n(.*?)(?=\n## |\Z)",
        "application": r"## 5\. 学习与应用\s*\n(.*?)(?=\n## |\Z)",
        "summary": r"## 6\. 总结\s*\n(.*?)(?=\n## |\Z)",
    }
    for key, pattern in sections.items():
        match = re.search(pattern, raw_text, re.DOTALL)
        if match:
            analysis[key] = match.group(1).strip()

    return analysis


def analyze_paper(paper):
    """Generate AI analysis for a paper."""
    prompt = ANALYSIS_PROMPT.format(
        title=paper["title"],
        authors=paper["authors"],
        venue=paper.get("venue", "Unknown"),
        abstract=paper["abstract"],
    )
    raw = call_llm(prompt)
    return parse_analysis(raw) if raw else None


# ============ Utilities ============

def deduplicate(papers):
    """Remove duplicates by normalized title."""
    seen = set()
    unique = []
    for p in papers:
        key = re.sub(r'[^a-z0-9]', '', p["title"].lower())[:80]
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def paper_id(paper):
    """Generate unique ID."""
    raw = f"{paper['title']}_{paper.get('date', '')}".encode()
    return hashlib.md5(raw).hexdigest()[:12]


def load_existing(filepath):
    """Load existing data file."""
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
    print("=" * 60)
    print("Paper Tracker - Daily Fetch & Analysis")
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
            time.sleep(4)

        # 2. OpenAlex (replaces Semantic Scholar - free, no strict rate limit)
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
            papers = fetch_biorxiv(keywords, max_results=5)
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

    # AI Analysis
    analyzed = 0
    if MODELSCOPE_API_KEY and all_new:
        print(f"\n--- AI Analysis ({len(all_new)} papers) ---")
        for paper in all_new:
            if analyzed >= MAX_ANALYSIS_PER_RUN:
                print(f"  Limit reached ({MAX_ANALYSIS_PER_RUN})")
                break
            print(f"  [{analyzed+1}] {paper['title'][:55]}...")
            analysis = analyze_paper(paper)
            if analysis:
                paper["analysis"] = analysis
                analyzed += 1
            else:
                print(f"    -> Failed, skipping")
            time.sleep(2)
    elif not MODELSCOPE_API_KEY:
        print("\n[WARN] No MODELSCOPE_API_KEY, skipping analysis")

    # Merge & save
    all_papers = all_new + existing["papers"]
    cutoff = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    all_papers = [p for p in all_papers if p.get("date", "9999") >= cutoff]
    all_papers.sort(key=lambda x: x.get("date", ""), reverse=True)
    all_papers = all_papers[:200]

    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "papers": all_papers,
    }
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Done! Papers: {len(all_papers)}, New: {len(all_new)}, Analyzed: {analyzed}")
    print(f"Saved: {data_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
