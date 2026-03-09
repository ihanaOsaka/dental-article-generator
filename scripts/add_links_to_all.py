"""全記事の参考文献にクリック可能なリンクを追加するスクリプト

処理フロー:
1. 記事から参考文献セクションを抽出
2. 各引用テキストからタイトル・著者・年を解析
3. PubMed API で検索し PMID/DOI を特定
4. 整合性チェック（タイトル・著者が一致するか）
5. Markdownリンク [引用](URL) に変換
6. 本文中の blockquote 引用にもリンクを追加
"""

import os
import re
import sys
import time
import urllib.parse

import httpx

# PubMed API レート制限: APIキーなしは3リクエスト/秒
RATE_LIMIT_DELAY = 0.4

# 学術引用パターン（参考文献セクション内）
# "1. 著者名. タイトル. *ジャーナル.* 年;巻(号):頁."
REF_LINE_PATTERN = re.compile(
    r'^(\d+)\.\s+'       # 番号
    r'(.+)$',            # 残り全部
    re.MULTILINE,
)

# ジャーナル名（イタリック）と年のパターン
JOURNAL_YEAR_PATTERN = re.compile(
    r'\*([^*]+)\.\*\s*'   # *ジャーナル名.*
    r'(\d{4})'            # 年
)

# 著者パターン（最初の著者名）
AUTHOR_PATTERN = re.compile(r'^([A-Z][a-zà-ü]+(?:\s[A-Z]{1,2})?)')

# 機関パターン（WHO, AAPD 等）
ORG_PATTERN = re.compile(r'^(WHO|AAPD|AAP|ADA|厚生労働省|日本小児歯科学会|日本歯科医師会)')

# 既存のMarkdownリンクパターン
EXISTING_LINK = re.compile(r'^\[.+\]\(https?://')

# blockquote引用パターン
BLOCKQUOTE_PATTERN = re.compile(r'^>\s*(.+)$', re.MULTILINE)

# WHO出版物のURL（既知のもの）
WHO_URLS = {
    "sugars intake": "https://www.who.int/publications/i/item/9789241549028",
    "fluoride": "https://www.who.int/publications/i/item/9789240096882",
    "breastfeeding": "https://www.who.int/health-topics/breastfeeding",
    "oral health": "https://www.who.int/news-room/fact-sheets/detail/oral-health",
}


def main():
    articles_dir = os.path.join(os.path.dirname(__file__), '..', 'output', 'articles')
    articles_dir = os.path.abspath(articles_dir)

    client = httpx.Client(
        timeout=15.0,
        follow_redirects=True,
        headers={"User-Agent": "DentalArticleBot/1.0 (reference linking)"},
    )

    files = sorted(f for f in os.listdir(articles_dir) if f.endswith('.md'))
    print(f"Processing {len(files)} articles...\n")

    total_links_added = 0

    for filename in files:
        filepath = os.path.join(articles_dir, filename)
        with open(filepath, encoding='utf-8') as f:
            text = f.read()

        # 既にリンク付きかチェック（infant_snack.md は処理済み）
        ref_section = extract_ref_section(text)
        if not ref_section:
            print(f"[SKIP] {filename}: 参考文献セクションなし")
            continue

        existing_links = len(re.findall(r'\[.+?\]\(https?://', ref_section))
        ref_lines = REF_LINE_PATTERN.findall(ref_section)

        if existing_links >= len(ref_lines) and existing_links > 0:
            print(f"[SKIP] {filename}: 既にリンク付き ({existing_links}件)")
            continue

        print(f"[PROC] {filename}: {len(ref_lines)}件の参考文献を処理中...")

        updated_text, links_added = process_article(text, ref_section, client)

        if links_added > 0:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(updated_text)
            total_links_added += links_added
            print(f"  -> {links_added}件のリンクを追加")
        else:
            print(f"  -> リンク追加なし")

    client.close()
    print(f"\n完了: 合計 {total_links_added} 件のリンクを追加")


def extract_ref_section(text: str) -> str:
    """参考文献セクションを抽出"""
    for marker in ["### 参考文献", "## 参考文献", "## References"]:
        if marker in text:
            return text[text.index(marker):]
    return ""


def process_article(text: str, ref_section: str, client: httpx.Client) -> tuple[str, int]:
    """記事を処理してリンクを追加"""
    links_added = 0
    updated_text = text

    for match in REF_LINE_PATTERN.finditer(ref_section):
        num = match.group(1)
        line_content = match.group(2).strip()
        original_line = match.group(0)

        # 既にリンク付きならスキップ
        if EXISTING_LINK.match(line_content) or '[' in line_content and '](http' in line_content:
            continue

        # 機関文献（WHO等）
        org_match = ORG_PATTERN.match(line_content)
        if org_match:
            url = find_org_url(line_content, org_match.group(1), client)
            if url:
                # 注釈部分（※...）を分離
                annotation = ""
                base_text = line_content
                if "※" in line_content:
                    parts = line_content.split("※", 1)
                    base_text = parts[0].strip()
                    annotation = " ※" + parts[1]

                new_line = f"{num}. [{base_text}]({url}){annotation}"
                updated_text = updated_text.replace(original_line, new_line, 1)
                links_added += 1
            continue

        # 学術引用
        result = search_pubmed(line_content, client)
        if result:
            pmid, doi, resolved_title = result
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            # 注釈部分を分離
            annotation = ""
            base_text = line_content
            if "※" in line_content:
                parts = line_content.split("※", 1)
                base_text = parts[0].strip()
                annotation = " ※" + parts[1]

            new_line = f"{num}. [{base_text}]({url}){annotation}"
            updated_text = updated_text.replace(original_line, new_line, 1)
            links_added += 1

            # 本文中の blockquote 引用にもリンク追加
            updated_text = add_blockquote_links(updated_text, line_content, url)

    return updated_text, links_added


def search_pubmed(citation: str, client: httpx.Client) -> tuple | None:
    """引用テキストからPubMedを検索してPMID/DOIを返す"""
    # 著者を抽出
    author_match = AUTHOR_PATTERN.match(citation)
    author = author_match.group(1) if author_match else ""

    # ジャーナルと年を抽出
    journal_year = JOURNAL_YEAR_PATTERN.search(citation)
    year = journal_year.group(2) if journal_year else ""
    journal = journal_year.group(1).strip() if journal_year else ""

    # タイトルを抽出（著者の後、ジャーナルの前）
    title = ""
    if author and journal_year:
        # 著者名の終わり（. の後）からジャーナルの前まで
        author_end = citation.find('. ', len(author))
        if author_end > 0:
            journal_start = citation.find('*')
            if journal_start > author_end:
                title = citation[author_end + 2:journal_start].strip().rstrip('.')

    if not title:
        # フォールバック: 引用テキスト全体の先頭部分を使う
        title = citation[:80]

    # PubMed検索（著者+年+ジャーナルで精密検索）
    queries = []

    if author and year and journal:
        # 最も精密な検索
        first_author_surname = author.split()[0]
        queries.append(
            f'{first_author_surname}[Author] AND {year}[Date - Publication]'
            f' AND "{journal}"[Journal]'
        )

    if title and len(title) > 20:
        # タイトルベースの検索
        # タイトルから特殊文字を除去
        clean_title = re.sub(r'[*_\[\]()]', '', title)
        queries.append(clean_title[:100])

    if author and year:
        # 著者+年
        first_author_surname = author.split()[0]
        queries.append(f'{first_author_surname}[Author] AND {year}[Date - Publication]')

    for query in queries:
        time.sleep(RATE_LIMIT_DELAY)
        try:
            encoded = urllib.parse.quote(query)
            url = (
                f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
                f"?db=pubmed&term={encoded}&retmode=json&retmax=5"
            )
            resp = client.get(url)
            data = resp.json()
            id_list = data.get("esearchresult", {}).get("idlist", [])

            if not id_list:
                continue

            # 候補から最も一致するものを選ぶ
            for pmid in id_list:
                time.sleep(RATE_LIMIT_DELAY)
                detail = get_pubmed_detail(pmid, client)
                if not detail or "error" in detail:
                    continue

                # 整合性チェック
                if check_consistency(citation, detail):
                    doi = ""
                    for aid in detail.get("articleids", []):
                        if aid.get("idtype") == "doi":
                            doi = aid.get("value", "")
                    return (pmid, doi, detail.get("title", ""))

        except Exception as e:
            print(f"    PubMed search error: {e}")
            continue

    return None


def get_pubmed_detail(pmid: str, client: httpx.Client) -> dict | None:
    """PubMed IDの詳細を取得"""
    try:
        url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            f"?db=pubmed&id={pmid}&retmode=json"
        )
        resp = client.get(url)
        data = resp.json()
        return data.get("result", {}).get(pmid)
    except Exception:
        return None


def check_consistency(citation: str, detail: dict) -> bool:
    """引用テキストとPubMedの論文情報の整合性チェック"""
    citation_lower = citation.lower()

    # 著者名チェック
    authors = detail.get("authors", [])
    if authors:
        first_author = ""
        if isinstance(authors[0], dict):
            first_author = authors[0].get("name", "").split()[0].lower()
        if first_author and len(first_author) > 2 and first_author in citation_lower:
            # 年チェック
            pub_date = detail.get("pubdate", "")
            year_match = re.search(r'(\d{4})', pub_date)
            if year_match and year_match.group(1) in citation:
                return True

    # タイトル部分一致
    pubmed_title = detail.get("title", "").lower()
    title_words = [w for w in pubmed_title.split()[:6]
                  if len(w) > 3 and w not in {"the", "and", "for", "with", "from", "that", "this"}]
    match_count = sum(1 for w in title_words if w in citation_lower)
    if match_count >= 2:
        return True

    # ジャーナル名チェック
    source = detail.get("source", "").lower()
    if source and len(source) > 3 and source in citation_lower:
        pub_date = detail.get("pubdate", "")
        year_match = re.search(r'(\d{4})', pub_date)
        if year_match and year_match.group(1) in citation:
            return True

    return False


def find_org_url(citation: str, org: str, client: httpx.Client) -> str:
    """機関文献のURLを特定"""
    citation_lower = citation.lower()

    # WHO: 既知のURLから検索
    if org == "WHO":
        for keyword, url in WHO_URLS.items():
            if keyword in citation_lower:
                return url
        return ""

    # AAPD/AAP/ADA: PubMedで検索してみる
    if org in ("AAPD", "AAP", "ADA"):
        result = search_pubmed(citation, client)
        if result:
            return f"https://pubmed.ncbi.nlm.nih.gov/{result[0]}/"

    # 日本の機関: リンクなし（日本語文献はPubMedに少ない）
    return ""


def add_blockquote_links(text: str, citation: str, url: str) -> str:
    """本文中のblockquote引用にもリンクを追加"""
    # 著者名と年を抽出して blockquote を検索
    author_match = AUTHOR_PATTERN.match(citation)
    if not author_match:
        return text

    journal_year = JOURNAL_YEAR_PATTERN.search(citation)
    if not journal_year:
        return text

    author = author_match.group(1)
    first_surname = author.split()[0]

    # blockquote行を検索
    for match in BLOCKQUOTE_PATTERN.finditer(text):
        line = match.group(1).strip()
        # この行がこの著者の引用かチェック
        if first_surname in line and not line.startswith('['):
            # 既にリンク付きでなければ追加
            if '](http' not in line:
                original = match.group(0)
                linked = f"> [{line}]({url})"
                text = text.replace(original, linked, 1)
                break

    return text


if __name__ == "__main__":
    os.chdir(os.path.join(os.path.dirname(__file__), '..'))
    main()
