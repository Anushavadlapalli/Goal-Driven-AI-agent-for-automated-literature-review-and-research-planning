from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_file
from flask_cors import CORS
import requests, os, json, hashlib, urllib3, time
from datetime import datetime
from collections import Counter
from io import BytesIO

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-development-secret")
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
USERS = {}


def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()


def groq_generate(prompt, retries=2):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 2048
    }
    for attempt in range(retries + 1):
        try:
            resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60, verify=False)
            if resp.status_code == 429:
                wait = min(int(resp.headers.get("Retry-After", 60)), 90)
                print(f"Rate limit — waiting {wait}s (attempt {attempt+1})")
                time.sleep(wait)
                continue
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.ConnectionError:
            raise Exception("Cannot connect to Groq API. Switch to mobile hotspot and try again.")
        except requests.exceptions.Timeout:
            if attempt < retries:
                time.sleep(5)
                continue
            raise Exception("Groq API timed out. Please try again.")
        except Exception as e:
            if attempt < retries:
                time.sleep(3)
                continue
            raise Exception(f"Groq error: {str(e)}")
    raise Exception("Groq API rate limit reached. Please wait 1 minute and try again.")


# ── Paper Search ──────────────────────────────────────────────

def _fetch_semantic(query, limit=50):
    """Fetch from Semantic Scholar — keep papers even without year."""
    try:
        params = {
            "query": query,
            "limit": limit,
            "fields": "title,authors,year,abstract,url,externalIds,openAccessPdf,citationCount,venue"
        }
        headers = {"User-Agent": "ResearchMindAI/1.0 (research project)"}
        resp = requests.get(SEMANTIC_SCHOLAR_API, params=params,
                            headers=headers, timeout=20, verify=False)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            # Keep papers that have a title — year optional
            return [p for p in data if p.get("title")]
        else:
            print(f"Semantic Scholar {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"Semantic Scholar error: {e}")
    return []


def _fetch_arxiv(topic, limit=20):
    """Fetch from arXiv XML API."""
    try:
        import urllib.parse, xml.etree.ElementTree as ET
        query = urllib.parse.quote(f'all:"{topic}"')
        url = f"http://export.arxiv.org/api/query?search_query={query}&start=0&max_results={limit}&sortBy=relevance&sortOrder=descending"
        resp = requests.get(url, timeout=20)
        if resp.status_code != 200:
            print(f"arXiv {resp.status_code}")
            return []
        root = ET.fromstring(resp.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        papers = []
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            summary = entry.find("atom:summary", ns)
            published = entry.find("atom:published", ns)
            link = entry.find("atom:id", ns)
            authors = entry.findall("atom:author", ns)
            author_names = [a.find("atom:name", ns).text for a in authors[:4]
                            if a.find("atom:name", ns) is not None]
            year_str = (published.text or "")[:4] if published is not None else ""
            year = int(year_str) if year_str.isdigit() else None
            arxiv_id = (link.text or "").strip() if link is not None else ""
            pdf_url = arxiv_id.replace("abs", "pdf") if "arxiv.org/abs" in arxiv_id else None
            title_text = (title.text or "Untitled").strip().replace("\n", " ")
            abstract_text = (summary.text or "").strip().replace("\n", " ")[:500]
            if title_text and title_text != "Untitled":
                papers.append({
                    "title": title_text,
                    "authors": [{"name": a} for a in author_names],
                    "year": year,
                    "abstract": abstract_text,
                    "url": arxiv_id,
                    "openAccessPdf": {"url": pdf_url} if pdf_url else None,
                    "externalIds": {},
                    "citationCount": 0,
                    "venue": "arXiv"
                })
        print(f"arXiv returned {len(papers)} papers")
        return papers
    except Exception as e:
        print(f"arXiv error: {e}")
    return []


def _fetch_arxiv_broad(topic, limit=20):
    """Broader arXiv search using individual keywords."""
    try:
        import urllib.parse, xml.etree.ElementTree as ET
        # Use ti: (title) + abs: (abstract) search
        words = topic.split()[:4]
        query_parts = [f'ti:{urllib.parse.quote(w)}' for w in words]
        query = "+OR+".join(query_parts)
        url = f"http://export.arxiv.org/api/query?search_query={query}&start=0&max_results={limit}&sortBy=relevance"
        resp = requests.get(url, timeout=20)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        papers = []
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            summary = entry.find("atom:summary", ns)
            published = entry.find("atom:published", ns)
            link = entry.find("atom:id", ns)
            authors = entry.findall("atom:author", ns)
            author_names = [a.find("atom:name", ns).text for a in authors[:4]
                            if a.find("atom:name", ns) is not None]
            year_str = (published.text or "")[:4] if published is not None else ""
            year = int(year_str) if year_str.isdigit() else None
            arxiv_id = (link.text or "").strip()
            pdf_url = arxiv_id.replace("abs", "pdf") if "arxiv.org/abs" in arxiv_id else None
            title_text = (title.text or "").strip().replace("\n", " ")
            if title_text:
                papers.append({
                    "title": title_text,
                    "authors": [{"name": a} for a in author_names],
                    "year": year,
                    "abstract": (summary.text or "").strip().replace("\n", " ")[:500],
                    "url": arxiv_id,
                    "openAccessPdf": {"url": pdf_url} if pdf_url else None,
                    "externalIds": {},
                    "citationCount": 0,
                    "venue": "arXiv"
                })
        print(f"arXiv broad returned {len(papers)} papers")
        return papers
    except Exception as e:
        print(f"arXiv broad error: {e}")
    return []


def search_papers(topic, limit=35):
    """Multi-source paper search — ensures at least papers are returned."""
    all_papers = []
    seen_titles = set()

    def add_papers(source_papers):
        for p in source_papers:
            if not isinstance(p, dict):
                continue
            t = (p.get("title") or "").lower().strip()
            # skip very short or empty titles
            if len(t) < 5 or t in seen_titles:
                continue
            seen_titles.add(t)
            all_papers.append(p)

    # Step 1: Semantic Scholar — full topic
    print(f"Searching Semantic Scholar for: {topic}")
    sem1 = _fetch_semantic(topic, 50)
    add_papers(sem1)
    print(f"After Semantic Scholar: {len(all_papers)} papers")

    # Step 2: arXiv — exact phrase
    if len(all_papers) < 15:
        print("Trying arXiv exact...")
        add_papers(_fetch_arxiv(topic, 25))
        print(f"After arXiv exact: {len(all_papers)} papers")

    # Step 3: Semantic Scholar — shortened query
    if len(all_papers) < 15:
        short = " ".join(topic.split()[:3])
        print(f"Trying Semantic Scholar short: {short}")
        add_papers(_fetch_semantic(short, 30))
        print(f"After Semantic short: {len(all_papers)} papers")

    # Step 4: arXiv broad keyword search
    if len(all_papers) < 15:
        print("Trying arXiv broad...")
        add_papers(_fetch_arxiv_broad(topic, 25))
        print(f"After arXiv broad: {len(all_papers)} papers")

    # Step 5: Single keyword fallback
    if len(all_papers) < 5:
        keyword = topic.split()[0]
        print(f"Fallback single keyword: {keyword}")
        add_papers(_fetch_arxiv(keyword, 20))
        add_papers(_fetch_semantic(keyword, 20))
        print(f"After fallback: {len(all_papers)} papers")

    # Sort: papers with year first (newest), then no-year papers
    with_year = sorted([p for p in all_papers if p.get("year")],
                       key=lambda x: x["year"], reverse=True)
    without_year = [p for p in all_papers if not p.get("year")]
    final = (with_year + without_year)[:limit]
    print(f"Final papers: {len(final)}")
    return final


def get_papers_by_year(topic, year):
    """Fetch papers specifically from a given year."""
    all_papers = []
    seen = set()

    # Semantic Scholar with year filter
    try:
        params = {
            "query": topic, "limit": 50,
            "fields": "title,authors,year,abstract,url,externalIds,openAccessPdf,citationCount,venue",
            "year": str(year)
        }
        resp = requests.get(SEMANTIC_SCHOLAR_API, params=params,
                            headers={"User-Agent": "ResearchMindAI/1.0"}, timeout=15, verify=False)
        if resp.status_code == 200:
            for p in resp.json().get("data", []):
                if not p.get("title"):
                    continue
                if p.get("year") and int(p.get("year")) != year:
                    continue
                t = p["title"].lower().strip()
                if t not in seen:
                    seen.add(t)
                    all_papers.append(p)
    except Exception as e:
        print(f"Year Semantic error: {e}")

    # arXiv year filter
    try:
        import urllib.parse, xml.etree.ElementTree as ET
        query = urllib.parse.quote(topic)
        url = f"http://export.arxiv.org/api/query?search_query=all:{query}&start=0&max_results=50&sortBy=relevance"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns):
                published = entry.find("atom:published", ns)
                if not published or not published.text:
                    continue
                pub_year = int(published.text[:4]) if published.text[:4].isdigit() else 0
                if pub_year != year:
                    continue
                title = entry.find("atom:title", ns)
                summary = entry.find("atom:summary", ns)
                link = entry.find("atom:id", ns)
                authors = entry.findall("atom:author", ns)
                author_names = [a.find("atom:name", ns).text for a in authors[:4]
                                if a.find("atom:name", ns) is not None]
                arxiv_id = (link.text or "").strip()
                pdf_url = arxiv_id.replace("abs", "pdf") if "arxiv.org/abs" in arxiv_id else None
                t_key = (title.text or "").lower().strip()
                if t_key and t_key not in seen:
                    seen.add(t_key)
                    all_papers.append({
                        "title": (title.text or "Untitled").strip().replace("\n", " "),
                        "authors": [{"name": a} for a in author_names],
                        "year": year,
                        "abstract": (summary.text or "").strip().replace("\n", " ")[:500],
                        "url": arxiv_id,
                        "openAccessPdf": {"url": pdf_url} if pdf_url else None,
                        "externalIds": {},
                        "citationCount": 0,
                        "venue": "arXiv"
                    })
    except Exception as e:
        print(f"Year arXiv error: {e}")

    all_papers.sort(key=lambda x: x.get("citationCount") or 0, reverse=True)
    return all_papers[:30]


def get_year_distribution(raw_papers):
    """Count papers by year from already-fetched list."""
    if not raw_papers or not isinstance(raw_papers, list):
        return {}
    year_counts = Counter()
    for p in raw_papers:
        if not isinstance(p, dict):
            continue
        y = p.get("year")
        if y and isinstance(y, int) and 2000 <= y <= 2026:
            year_counts[y] += 1
    if not year_counts:
        return {}
    return {str(y): int(year_counts[y]) for y in sorted(year_counts.keys())}


def get_ai_summary(topic, papers):
    pt = ""
    for i, p in enumerate(papers[:5]):
        if not isinstance(p, dict):
            continue
        authors = ', '.join([a.get('name', '') for a in p.get('authors', [])[:3]])
        pt += f"\n{i+1}. {p.get('title')} — {authors} ({p.get('year', 'N/A')})\n   {(p.get('abstract') or '')[:300]}\n"

    prompt = f"""You are an expert research analyst researching: "{topic}"
Papers found:
{pt if pt.strip() else "Use your own knowledge about this topic."}

RULES: ONLY bullet points (-). No paragraphs. No ** markers.

## BRIEF INTRODUCTION
- [what this topic is]
- [why it matters]
- [where it is applied]
- [recent growth/importance]

## CURRENT STATE OF RESEARCH
- [latest finding 1]
- [latest finding 2]
- [latest finding 3]
- [latest finding 4]
- [latest finding 5]

## RESEARCH GAPS & OPPORTUNITIES
- [open problem 1]
- [open problem 2]
- [open problem 3]
- [open problem 4]

## DATASETS MENTIONED
List EXACTLY 3 real benchmark DATASETS for "{topic}".
ONLY real academic datasets (ImageNet, MNIST, COCO, SQuAD, GLUE, KITTI, CelebA, MIMIC-III etc.)
NO libraries, NO frameworks.

- Dataset Name: [name]
- Domain: [domain]
- Description: [one sentence]
- Dataset Name: [name]
- Domain: [domain]
- Description: [one sentence]
- Dataset Name: [name]
- Domain: [domain]
- Description: [one sentence]"""
    return groq_generate(prompt)


def get_literature_review(topic, papers):
    valid = [p for p in papers[:10] if isinstance(p, dict)]
    top3 = valid[:3]

    intro_ctx = ""
    for i, p in enumerate(top3):
        authors = ', '.join([a.get('name', '') for a in p.get('authors', [])[:3]])
        intro_ctx += f"\nPaper {i+1}: {p.get('title')} by {authors} ({p.get('year', 'N/A')})\nAbstract: {(p.get('abstract') or '')[:400]}\n"

    lit_ctx = ""
    for p in valid:
        authors = ', '.join([a.get('name', '') for a in p.get('authors', [])[:2]])
        lit_ctx += f"\n- {p.get('title')} by {authors} ({p.get('year', 'N/A')}): {(p.get('abstract') or '')[:200]}"

    prompt = f"""You are a research scholar writing a formal academic document on: "{topic}"

SOURCE PAPERS:
{intro_ctx}

ALL PAPERS FOR REVIEW:
{lit_ctx}

Write in formal academic style, proper paragraphs only (NO bullet points):

## INTRODUCTION
5 paragraphs (~600 words):
- Para 1: Background and importance of {topic}
- Para 2: Key challenges and limitations in this area
- Para 3: What Paper 1 and Paper 2 found (cite as Author, Year)
- Para 4: What Paper 3 contributes and broader trends
- Para 5: Scope and objectives of this review

## LITERATURE REVIEW
Comprehensive review (~500 words) of ALL papers above.
For each: problem solved, method/dataset, findings, limitations.
Use (Author, Year) citations. End with synthesis paragraph."""

    return groq_generate(prompt)


def parse_sections(text):
    sections, cur, content = {}, None, []
    for line in text.split('\n'):
        if line.startswith('## '):
            if cur:
                sections[cur] = '\n'.join(content).strip()
            cur = line[3:].strip()
            content = []
        else:
            content.append(line)
    if cur:
        sections[cur] = '\n'.join(content).strip()
    return sections


def extract_datasets(sections):
    datasets, current = [], {}
    for line in sections.get("DATASETS MENTIONED", "").split('\n'):
        line = line.strip()
        if 'Dataset Name:' in line:
            if current and 'name' in current:
                datasets.append(current)
            current = {'name': line.split('Dataset Name:')[-1].strip().strip('-').strip()}
        elif 'Domain:' in line and current:
            current['domain'] = line.split('Domain:')[-1].strip()
        elif 'Description:' in line and current:
            current['description'] = line.split('Description:')[-1].strip()
    if current and 'name' in current:
        datasets.append(current)
    return datasets


def format_papers(raw):
    out = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        authors = [a.get("name", "") for a in p.get("authors", [])[:4]]
        pdf_url = (p.get("openAccessPdf") or {}).get("url")
        ext = p.get("externalIds") or {}
        url = f"https://doi.org/{ext['DOI']}" if ext.get("DOI") else p.get("url")
        out.append({
            "title": p.get("title", "Untitled"),
            "authors": authors,
            "year": p.get("year") or "N/A",
            "abstract": (p.get("abstract") or "")[:400],
            "url": url,
            "pdf_url": pdf_url,
            "citation_count": p.get("citationCount", 0),
            "venue": p.get("venue", "")
        })
    return out


def generate_pdf(topic, papers, intro_text, lit_review_text, sections):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2.5*cm, rightMargin=2.5*cm,
                            topMargin=2.5*cm, bottomMargin=2.5*cm)
    styles = getSampleStyleSheet()
    PRIMARY = colors.HexColor('#1d4ed8')
    DARK    = colors.HexColor('#0f172a')
    MUTED   = colors.HexColor('#475569')
    LIGHT   = colors.HexColor('#e2e8f0')

    ts = ParagraphStyle('T', parent=styles['Title'], fontSize=22, textColor=PRIMARY,
                        spaceAfter=6, alignment=TA_CENTER, fontName='Helvetica-Bold')
    ss = ParagraphStyle('S', parent=styles['Normal'], fontSize=11, textColor=MUTED,
                        spaceAfter=4, alignment=TA_CENTER)
    h1s = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=15, textColor=PRIMARY,
                         spaceBefore=18, spaceAfter=8, fontName='Helvetica-Bold')
    bs = ParagraphStyle('B', parent=styles['Normal'], fontSize=10, textColor=DARK,
                        spaceAfter=6, leading=16, alignment=TA_JUSTIFY)
    bls = ParagraphStyle('BL', parent=styles['Normal'], fontSize=10, textColor=DARK,
                         spaceAfter=4, leading=15, leftIndent=16)
    pts = ParagraphStyle('PT', parent=styles['Normal'], fontSize=10, textColor=PRIMARY,
                         spaceAfter=2, fontName='Helvetica-Bold')
    pms = ParagraphStyle('PM', parent=styles['Normal'], fontSize=9, textColor=MUTED, spaceAfter=2)
    pas = ParagraphStyle('PA', parent=styles['Normal'], fontSize=9, textColor=DARK,
                         spaceAfter=8, leading=13, leftIndent=8)
    team_s = ParagraphStyle('team', parent=styles['Normal'], fontSize=10, textColor=MUTED,
                             alignment=TA_CENTER, spaceAfter=3)
    lnk_s = ParagraphStyle('lnk', parent=styles['Normal'], fontSize=9, textColor=PRIMARY, spaceAfter=10)

    story = []
    now = datetime.now().strftime("%d %B %Y")
    story += [Spacer(1, 1.5*cm),
              Paragraph("ResearchMind AI", ss), Spacer(1, 0.3*cm),
              Paragraph("Literature Review Report", ts), Spacer(1, 0.2*cm),
              Paragraph(f"Topic: {topic}", ParagraphStyle('tp', parent=styles['Normal'],
                         fontSize=13, textColor=DARK, alignment=TA_CENTER, fontName='Helvetica-Bold')),
              Spacer(1, 0.3*cm),
              Paragraph(f"Generated on {now}  ·  {len(papers)} papers analyzed", ss),
              Spacer(1, 0.5*cm), HRFlowable(width="100%", thickness=2, color=PRIMARY),
              Spacer(1, 0.4*cm),
              Paragraph("Team: P. Bharani · Ch. Bharathi · V. Anusha · K. Deena Flarance", team_s),
              Paragraph("Guide: Dr. K. Prasanthi", team_s), PageBreak()]

    # Introduction
    story.append(Paragraph("1. Introduction", h1s))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT))
    story.append(Spacer(1, 0.2*cm))
    intro_clean = intro_text.split("## LITERATURE REVIEW")[0].replace("## INTRODUCTION", "").strip()
    for p in intro_clean.split('\n\n'):
        p = p.strip()
        if p:
            story.append(Paragraph(p.replace('\n', ' '), bs))
    story.append(Spacer(1, 0.4*cm))

    # Literature Review
    story.append(Paragraph("2. Literature Review", h1s))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT))
    story.append(Spacer(1, 0.2*cm))
    lit_clean = (intro_text.split("## LITERATURE REVIEW")[-1].strip()
                 if "## LITERATURE REVIEW" in intro_text else lit_review_text)
    for p in lit_clean.split('\n\n'):
        p = p.strip()
        if p:
            story.append(Paragraph(p.replace('\n', ' '), bs))
    story.append(Spacer(1, 0.4*cm))

    # 3 sections only
    for sec_key, sec_title in [
        ('BRIEF INTRODUCTION', '3. Brief Introduction'),
        ('CURRENT STATE OF RESEARCH', '4. Current State of Research'),
        ('RESEARCH GAPS & OPPORTUNITIES', '5. Research Gaps & Opportunities'),
    ]:
        sec_content = sections.get(sec_key, '')
        if not sec_content:
            continue
        story.append(Paragraph(sec_title, h1s))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT))
        story.append(Spacer(1, 0.2*cm))
        for line in sec_content.split('\n'):
            line = line.replace('- ', '').strip()
            if line and not line.startswith('##'):
                story.append(Paragraph(f"• {line}", bls))
        story.append(Spacer(1, 0.3*cm))

    # Papers
    story.append(PageBreak())
    story.append(Paragraph(f"6. Research Papers ({len(papers)} papers)", h1s))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT))
    story.append(Spacer(1, 0.3*cm))
    for i, p in enumerate(papers):
        authors_str = ', '.join(p.get('authors', [])[:3])
        if len(p.get('authors', [])) > 3:
            authors_str += ' et al.'
        story.append(Paragraph(f"{i+1}. {p['title']}", pts))
        meta = f"Authors: {authors_str or 'Unknown'}   |   Year: {p.get('year','N/A')}   |   Citations: {p.get('citation_count',0)}"
        if p.get('venue'):
            meta += f"   |   {p['venue']}"
        story.append(Paragraph(meta, pms))
        if p.get('abstract'):
            story.append(Paragraph(p['abstract'], pas))
        if p.get('url'):
            story.append(Paragraph(f"<link href='{p['url']}'><u>View Article</u></link>", lnk_s))
        story.append(HRFlowable(width="100%", thickness=0.3, color=LIGHT))
        story.append(Spacer(1, 0.2*cm))

    doc.build(story)
    buf.seek(0)
    return buf


# ── Routes ────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['user'])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        if not name or not email or not password:
            return jsonify({"error": "All fields required"}), 400
        if email in USERS:
            return jsonify({"error": "already_exists"}), 400
        if len(password) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400
        if not any(c.isupper() for c in password):
            return jsonify({"error": "Password must have at least one uppercase letter"}), 400
        if not any(c.isdigit() for c in password):
            return jsonify({"error": "Password must have at least one number"}), 400
        USERS[email] = {"name": name, "email": email, "password": hash_password(password)}
        return jsonify({"success": True, "redirect": "/login"})
    return render_template('auth.html', mode='register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        user = USERS.get(email)
        if not user or user['password'] != hash_password(password):
            return jsonify({"error": "Invalid email or password"}), 401
        session['user'] = user['name']
        session['email'] = email
        return jsonify({"success": True, "name": user['name']})
    return render_template('auth.html', mode='login')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/research', methods=['POST'])
def research():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    topic = data.get('topic', '').strip()
    if not topic:
        return jsonify({"error": "Topic is required"}), 400
    try:
        raw_papers = search_papers(topic, limit=35)
        summary_text = get_ai_summary(topic, raw_papers)
        sections = parse_sections(summary_text)
        datasets = extract_datasets(sections)
        papers = format_papers(raw_papers)
        year_dist = get_year_distribution(raw_papers)   # ✅ raw_papers list
        lit_text = get_literature_review(topic, raw_papers)
        lit_sections = parse_sections(lit_text)
        return jsonify({
            "topic": topic,
            "summary_text": summary_text,
            "sections": sections,
            "datasets": datasets,
            "papers": papers,
            "paper_count": len(papers),
            "year_distribution": year_dist,
            "introduction": lit_sections.get("INTRODUCTION", ""),
            "literature_review": lit_sections.get("LITERATURE REVIEW", ""),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/papers-by-year', methods=['POST'])
def papers_by_year():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    topic = data.get('topic', '').strip()
    year = data.get('year')
    if not topic or not year:
        return jsonify({"error": "Topic and year required"}), 400
    try:
        raw = get_papers_by_year(topic, int(year))
        papers = format_papers(raw)
        return jsonify({"papers": papers, "year": year, "count": len(papers)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download-pdf', methods=['POST'])
def download_pdf():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    topic = data.get('topic', 'Research')
    papers = data.get('papers', [])
    sections = data.get('sections', {})
    introduction = data.get('introduction', '')
    literature_review = data.get('literature_review', '')
    combined = f"## INTRODUCTION\n{introduction}\n\n## LITERATURE REVIEW\n{literature_review}"
    try:
        pdf_buf = generate_pdf(topic, papers, combined, literature_review, sections)
        filename = topic.replace(' ', '_')[:40] + '_LitReview.pdf'
        return send_file(pdf_buf, mimetype='application/pdf',
                         as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/audio', methods=['POST'])
def generate_audio():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    text = data.get('text', '')
    topic = data.get('topic', 'Research Summary')
    if not text:
        return jsonify({"error": "Text required"}), 400
    try:
        script = groq_generate(
            f'Convert to a natural spoken audio script under 350 words. '
            f'Remove all markdown. Start: "Research Summary on {topic}."\nText: {text[:1500]}'
        )
        return jsonify({"audio_script": script, "topic": topic})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)