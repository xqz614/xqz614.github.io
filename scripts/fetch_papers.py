#!/usr/bin/env python3
"""
Daily Paper Fetcher & AI Analyzer
Fetches papers from arXiv, bioRxiv, and Semantic Scholar,
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

# Research directions and their search queries
RESEARCH_DIRECTIONS = {
    "medical": {
        "name": "医疗对话系统 / Medical Dialogue & NLP",
        "arxiv_queries": [
            'cat:cs.CL AND (abs:"medical dialogue" OR abs:"clinical dialogue" OR abs:"healthcare conversation")',
            'cat:cs.CL AND (abs:"medical NLP" OR abs:"clinical NLP" OR abs:"biomedical NLP")',
            'cat:cs.AI AND (abs:"medical agent" OR abs:"clinical agent" OR abs:"health agent")',
            'cat:cs.CL AND (abs:"medical question answering" OR abs:"clinical QA")',
        ],
        "semantic_scholar_queries": [
            "medical dialogue system LLM",
            "clinical NLP large language model",
            "medical agent healthcare",
        ],
        "biorxiv_queries": [
            "clinical dialogue AI",
            "medical NLP",
        ],
    },
    "cell": {
        "name": "虚拟细胞 / Virtual Cell",
        "arxiv_queries": [
            'cat:q-bio.QM AND (abs:"virtual cell" OR abs:"cell simulation" OR abs:"perturbation prediction")',
            'cat:q-bio.GN AND (abs:"gene expression prediction" OR abs:"single cell" OR abs:"combinatorial perturbation")',
            'cat:cs.LG AND abs:"single cell" AND (abs:"perturbation" OR abs:"gene expression")',
        ],
        "semantic_scholar_queries": [
            "virtual cell model single cell",
            "perturbation prediction gene expression deep learning",
            "foundation model single cell genomics",
        ],
        "biorxiv_queries": [
            "virtual cell model",
            "perturbation prediction single cell",
            "gene expression prediction deep learning",
        ],
    },
    "llm": {
        "name": "大模型与NLP / LLM & NLP Frontiers",
        "arxiv_queries": [
            'cat:cs.CL AND (abs:"large language model" OR abs:"LLM") AND (abs:"reasoning" OR abs:"alignment" OR abs:"agent")',
            'cat:cs.CL AND (abs:"reinforcement learning" AND abs:"language model")',
            'cat:cs.AI AND (abs:"foundation model" OR abs:"multimodal") AND abs:"language"',
            'cat:cs.CL AND (abs:"retrieval augmented" OR abs:"RAG" OR abs:"in-context learning")',
        ],
        "semantic_scholar_queries": [
            "large language model reasoning 2026",
            "LLM agent reinforcement learning",
            "multimodal foundation model",
        ],
        "biorxiv_queries": [],
    },
}

# Top venues to track
TOP_VENUES = [
    "ACL", "EMNLP", "NAACL", "COLING",
    "NeurIPS", "ICML", "ICLR", "AAAI",
    "Nature", "Nature Medicine", "Nature Methods",
    "Nature Biotechnology", "Nature Machine Intelligence",
    "Cell", "Cell Systems",
    "The Lancet Digital Health",
    "JAMIA", "Journal of Biomedical Informatics",
    "Bioinformatics", "Genome Research",
    "ACM Computing Surveys", "JMLR",
]

MAX_PAPERS_PER_DIRECTION = 15
MAX_ANALYSIS_PER_RUN = 30  # Limit API calls per run

# ============ Paper Fetching ============

def fetch_arxiv_papers(query, max_results=10):
    """Fetch papers from arXiv API."""
    papers = []
    try:
        base_url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; PaperTracker/1.0)"})

        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read().decode("utf-8")

        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        root = ET.fromstring(data)

        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
            abstract = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
            published = entry.find("atom:published", ns).text[:10]
            arxiv_id = entry.find("atom:id", ns).text.split("/abs/")[-1]

            authors = []
            for author in entry.findall("atom:author", ns):
                name = author.find("atom:name", ns).text
                authors.append(name)

            paper_url = f"https://arxiv.org/abs/{arxiv_id}"
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

            papers.append({
                "title": title,
                "authors": ", ".join(authors[:5]) + ("..." if len(authors) > 5 else ""),
                "abstract": abstract,
                "date": published,
                "url": paper_url,
                "pdf_url": pdf_url,
                "source": "arxiv",
                "venue": "arXiv",
                "arxiv_id": arxiv_id,
            })
    except Exception as e:
        print(f"  [WARN] arXiv fetch error for query '{query[:50]}...': {e}")

    return papers


def fetch_biorxiv_papers(query, max_results=5):
    """Fetch papers from bioRxiv/medRxiv API."""
    papers = []
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        url = f"https://api.biorxiv.org/details/biorxiv/{start_date}/{end_date}/0/50"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; PaperTracker/1.0)"})

        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))

        query_terms = query.lower().split()
        for item in data.get("collection", []):
            title = item.get("title", "")
            abstract = item.get("abstract", "")
            combined = (title + " " + abstract).lower()

            if any(term in combined for term in query_terms):
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

        papers = papers[:max_results]
    except Exception as e:
        print(f"  [WARN] bioRxiv fetch error for query '{query}': {e}")

    return papers


def fetch_semantic_scholar_papers(query, max_results=5):
    """Fetch papers from Semantic Scholar API (covers conferences & journals)."""
    papers = []
    try:
        base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": max_results,
            "fields": "title,authors,abstract,year,venue,externalIds,url,publicationDate",
            "year": f"{datetime.now().year - 1}-{datetime.now().year}",
        }
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; PaperTracker/1.0)"})

        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))

        for item in data.get("data", []):
            if not item.get("abstract"):
                continue

            authors = ", ".join([a.get("name", "") for a in (item.get("authors") or [])[:5]])
            if len(item.get("authors", [])) > 5:
                authors += "..."

            venue = item.get("venue", "")
            ext_ids = item.get("externalIds") or {}
            arxiv_id = ext_ids.get("ArXiv", "")
            doi = ext_ids.get("DOI", "")

            # Determine source type
            source = "conference"
            if venue:
                venue_lower = venue.lower()
                if any(j.lower() in venue_lower for j in ["nature", "cell", "lancet", "journal", "transactions", "review"]):
                    source = "journal"
            elif arxiv_id:
                source = "arxiv"

            paper_url = item.get("url", "")
            if arxiv_id:
                paper_url = f"https://arxiv.org/abs/{arxiv_id}"

            pub_date = item.get("publicationDate", "")
            if not pub_date:
                pub_date = f"{item.get('year', datetime.now().year)}-01-01"

            papers.append({
                "title": item.get("title", ""),
                "authors": authors,
                "abstract": item.get("abstract", ""),
                "date": pub_date,
                "url": paper_url,
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
                "source": source,
                "venue": venue or ("arXiv" if arxiv_id else ""),
            })
    except Exception as e:
        print(f"  [WARN] Semantic Scholar fetch error for query '{query}': {e}")

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


def call_llm(prompt, max_retries=3):
    """Call ModelScope Qwen API using OpenAI-compatible interface."""
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
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"]
                # Remove thinking tags if present
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                return content
        except Exception as e:
            print(f"  [WARN] LLM call attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))

    return None


def parse_analysis(raw_text):
    """Parse LLM output into structured analysis."""
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

    # Extract pipeline steps from summary
    pipeline_match = re.search(r'[pP]ipeline.*?[：:]\s*\n?(.*?)(?=\n\n|\Z)', raw_text, re.DOTALL)
    if pipeline_match:
        steps_text = pipeline_match.group(1)
        steps = re.findall(r'(?:\d+[\.\)]\s*|[→➜>]\s*)(.*?)(?=\n|$)', steps_text)
        if steps:
            analysis["pipeline_steps"] = [s.strip() for s in steps if s.strip()]

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
    if raw:
        return parse_analysis(raw)
    return None


# ============ Main Pipeline ============

def deduplicate_papers(papers):
    """Remove duplicate papers based on title similarity."""
    seen = set()
    unique = []
    for p in papers:
        # Normalize title for dedup
        key = re.sub(r'[^a-z0-9]', '', p["title"].lower())[:80]
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def generate_paper_id(paper):
    """Generate a unique ID for a paper."""
    raw = f"{paper['title']}_{paper.get('date', '')}".encode()
    return hashlib.md5(raw).hexdigest()[:12]


def load_existing_data(filepath):
    """Load existing papers data."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_updated": "", "papers": []}


def main():
    print("=" * 60)
    print("Paper Tracker - Daily Fetch & Analysis")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Paths
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    data_file = project_dir / "papers" / "papers_data.json"
    data_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data
    existing = load_existing_data(data_file)
    existing_ids = {p["id"] for p in existing["papers"]}

    all_new_papers = []

    for direction, config in RESEARCH_DIRECTIONS.items():
        print(f"\n--- Fetching: {config['name']} ---")
        direction_papers = []

        # Fetch from arXiv
        for query in config["arxiv_queries"]:
            print(f"  arXiv: {query[:60]}...")
            papers = fetch_arxiv_papers(query, max_results=5)
            direction_papers.extend(papers)
            time.sleep(5)  # Rate limiting for arXiv

        # Fetch from bioRxiv
        for query in config.get("biorxiv_queries", []):
            if query:
                print(f"  bioRxiv: {query}")
                papers = fetch_biorxiv_papers(query, max_results=3)
                direction_papers.extend(papers)
                time.sleep(1)

        # Fetch from Semantic Scholar (covers conferences & journals)
        for query in config.get("semantic_scholar_queries", []):
            print(f"  Semantic Scholar: {query}")
            papers = fetch_semantic_scholar_papers(query, max_results=5)
            direction_papers.extend(papers)
            time.sleep(5)  # Rate limiting for Semantic Scholar

        # Deduplicate
        direction_papers = deduplicate_papers(direction_papers)

        # Add direction and ID
        for p in direction_papers:
            p["direction"] = direction
            p["id"] = generate_paper_id(p)

        # Filter out already existing papers
        new_papers = [p for p in direction_papers if p["id"] not in existing_ids]

        # Sort by date and limit
        new_papers.sort(key=lambda x: x.get("date", ""), reverse=True)
        new_papers = new_papers[:MAX_PAPERS_PER_DIRECTION]

        print(f"  Found {len(direction_papers)} total, {len(new_papers)} new papers")
        all_new_papers.extend(new_papers)

    # Generate AI analysis for new papers
    analysis_count = 0
    if MODELSCOPE_API_KEY and all_new_papers:
        print(f"\n--- Generating AI Analysis ({len(all_new_papers)} papers) ---")
        for paper in all_new_papers:
            if analysis_count >= MAX_ANALYSIS_PER_RUN:
                print(f"  Reached analysis limit ({MAX_ANALYSIS_PER_RUN}), stopping.")
                break

            print(f"  Analyzing: {paper['title'][:60]}...")
            analysis = analyze_paper(paper)
            if analysis:
                paper["analysis"] = analysis
                analysis_count += 1
                print(f"    -> Analysis generated ({analysis_count}/{MAX_ANALYSIS_PER_RUN})")
            else:
                print(f"    -> Analysis failed, skipping")

            time.sleep(2)  # Rate limiting
    else:
        if not MODELSCOPE_API_KEY:
            print("\n[WARN] MODELSCOPE_API_KEY not set, skipping analysis")

    # Merge with existing data
    all_papers = all_new_papers + existing["papers"]

    # Keep only last 60 days of papers, max 200 total
    cutoff = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    all_papers = [p for p in all_papers if p.get("date", "9999") >= cutoff]
    all_papers.sort(key=lambda x: x.get("date", ""), reverse=True)
    all_papers = all_papers[:200]

    # Save
    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "papers": all_papers,
    }

    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Done! Total papers: {len(all_papers)}, New: {len(all_new_papers)}, Analyzed: {analysis_count}")
    print(f"Data saved to: {data_file}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
