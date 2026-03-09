"""参考文献リンク検証サービス"""

import logging
import re
import sys
import urllib.parse
from pathlib import Path

import httpx

_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.state import VerificationResult

logger = logging.getLogger(__name__)

# DOIパターン
DOI_PATTERN = re.compile(r'(10\.\d{4,}/[^\s\)"\]]+)')
# PMIDパターン
PMID_URL_PATTERN = re.compile(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)')
PMID_TEXT_PATTERN = re.compile(r'PMID[:\s]*(\d+)')
# 一般URLパターン
URL_PATTERN = re.compile(r'https?://[^\s\)"\]>]+')
# 学術引用パターン: "著者. タイトル. *ジャーナル.* 年;巻(号):頁."
CITATION_PATTERN = re.compile(
    r'^\d+\.\s+'                        # 番号
    r'(.+?)\.\s+'                       # 著者
    r'(.+?)\.\s+'                       # タイトル
    r'\*(.+?)\.\*\s*'                   # ジャーナル（イタリック）
    r'(\d{4})',                          # 年
    re.MULTILINE,
)
# ガイドライン・機関文献パターン（WHO, AAPD等）
GUIDELINE_PATTERN = re.compile(
    r'^\d+\.\s+'
    r'(WHO|AAPD|AAP|ADA|厚生労働省|日本小児歯科学会)[.\s]+'
    r'(.+?)$',
    re.MULTILINE,
)


class ReferenceVerifier:
    """記事内の参考文献リンクを検証"""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "DentalArticleBot/1.0 (reference verification)"},
        )

    def verify_article(self, article_text: str) -> list[VerificationResult]:
        """記事全体の参考文献を検証"""
        references = self._extract_references(article_text)
        results = []

        for ref in references:
            result = self._verify_reference(ref)
            if result:
                results.append(result)

        return results

    def _extract_references(self, text: str) -> list[dict]:
        """記事テキストから参考文献情報を抽出"""
        refs = []
        seen = set()

        # 参考文献セクションを探す
        ref_section = ""
        for marker in ["### 参考文献", "## 参考文献", "## References", "参考文献"]:
            if marker in text:
                ref_section = text[text.index(marker):]
                break
        if not ref_section:
            ref_section = text

        # 1. 既存のDOI/PMID/URLを抽出
        for match in DOI_PATTERN.finditer(ref_section):
            doi = match.group(1).rstrip(".,;")
            key = f"doi:{doi}"
            if key not in seen:
                context = self._get_context(ref_section, match.start())
                refs.append({"url": f"https://doi.org/{doi}", "type": "DOI",
                           "context": context, "doi": doi})
                seen.add(key)

        for match in PMID_URL_PATTERN.finditer(ref_section):
            pmid = match.group(1)
            key = f"pmid:{pmid}"
            if key not in seen:
                context = self._get_context(ref_section, match.start())
                refs.append({"url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                           "type": "PMID", "context": context, "pmid": pmid})
                seen.add(key)

        for match in PMID_TEXT_PATTERN.finditer(ref_section):
            pmid = match.group(1)
            key = f"pmid:{pmid}"
            if key not in seen:
                context = self._get_context(ref_section, match.start())
                refs.append({"url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                           "type": "PMID", "context": context, "pmid": pmid})
                seen.add(key)

        for match in URL_PATTERN.finditer(ref_section):
            url = match.group(0).rstrip(".,;)")
            if url not in seen and "doi.org" not in url and "pubmed.ncbi" not in url:
                context = self._get_context(ref_section, match.start())
                refs.append({"url": url, "type": "URL", "context": context})
                seen.add(url)

        # 2. 学術引用形式（URLなし）をPubMed検索で解決
        for match in CITATION_PATTERN.finditer(ref_section):
            authors = match.group(1).strip()
            title = match.group(2).strip()
            journal = match.group(3).strip()
            year = match.group(4).strip()
            context_line = match.group(0).strip()
            key = f"citation:{title[:50]}"

            if key not in seen:
                refs.append({
                    "type": "CITATION",
                    "context": context_line,
                    "title": title,
                    "authors": authors,
                    "journal": journal,
                    "year": year,
                    "url": "",
                })
                seen.add(key)

        # 3. ガイドライン文献
        for match in GUIDELINE_PATTERN.finditer(ref_section):
            org = match.group(1).strip()
            desc = match.group(2).strip()
            context_line = match.group(0).strip()
            key = f"guideline:{org}:{desc[:30]}"

            if key not in seen:
                refs.append({
                    "type": "GUIDELINE",
                    "context": context_line,
                    "organization": org,
                    "description": desc,
                    "url": "",
                })
                seen.add(key)

        return refs

    def _verify_reference(self, ref: dict) -> VerificationResult | None:
        """個別の参考文献を検証"""
        ref_type = ref["type"]

        try:
            if ref_type == "PMID":
                return self._verify_pmid(ref)
            elif ref_type == "DOI":
                return self._verify_doi(ref)
            elif ref_type == "URL":
                return self._verify_url(ref)
            elif ref_type == "CITATION":
                return self._verify_citation(ref)
            elif ref_type == "GUIDELINE":
                return self._verify_guideline(ref)
        except httpx.TimeoutException:
            return VerificationResult(
                reference_text=ref.get("context", ""),
                url=ref.get("url", ""),
                ref_type=ref_type,
                status="timeout",
                error_message="接続タイムアウト",
            )
        except Exception as e:
            return VerificationResult(
                reference_text=ref.get("context", ""),
                url=ref.get("url", ""),
                ref_type=ref_type,
                status="error",
                error_message=str(e),
            )
        return None

    def _verify_citation(self, ref: dict) -> VerificationResult:
        """学術引用をPubMed検索で確認"""
        title = ref["title"]
        authors = ref["authors"]
        year = ref["year"]

        # 第一著者の姓を取得
        first_author = authors.split(",")[0].strip().split(" ")[0]

        # PubMed検索
        query = f"{title}"
        encoded_query = urllib.parse.quote(query)
        search_url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pubmed&term={encoded_query}&retmode=json&retmax=3"
        )
        response = self.client.get(search_url)
        data = response.json()

        id_list = data.get("esearchresult", {}).get("idlist", [])

        if id_list:
            pmid = id_list[0]
            # PMIDの詳細を取得してタイトルを確認
            detail = self._get_pubmed_detail(pmid)
            pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            return VerificationResult(
                reference_text=ref["context"],
                url=pubmed_url,
                ref_type="CITATION",
                status="valid",
                http_status=200,
                resolved_title=detail.get("title", ""),
            )
        else:
            return VerificationResult(
                reference_text=ref["context"],
                url="",
                ref_type="CITATION",
                status="not_found",
                error_message=f"PubMedで「{title[:50]}...」が見つかりませんでした",
            )

    def _verify_guideline(self, ref: dict) -> VerificationResult:
        """ガイドライン文献を検証（機関名ベース）"""
        org = ref["organization"]
        desc = ref["description"]

        # まずPubMedで検索
        query = f"{org} {desc[:60]}"
        encoded_query = urllib.parse.quote(query)
        search_url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pubmed&term={encoded_query}&retmode=json&retmax=3"
        )

        try:
            response = self.client.get(search_url)
            data = response.json()
            id_list = data.get("esearchresult", {}).get("idlist", [])

            if id_list:
                pmid = id_list[0]
                detail = self._get_pubmed_detail(pmid)
                pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                return VerificationResult(
                    reference_text=ref["context"],
                    url=pubmed_url,
                    ref_type="GUIDELINE",
                    status="valid",
                    http_status=200,
                    resolved_title=detail.get("title", ""),
                )
        except Exception:
            pass

        # PubMedで見つからない場合（WHO等の独自出版物）
        return VerificationResult(
            reference_text=ref["context"],
            url="",
            ref_type="GUIDELINE",
            status="not_found",
            error_message=f"{org}のガイドラインはPubMedで検索できませんでした（機関サイトで確認が必要）",
        )

    def _get_pubmed_detail(self, pmid: str) -> dict:
        """PubMed IDの詳細情報を取得"""
        api_url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            f"?db=pubmed&id={pmid}&retmode=json"
        )
        response = self.client.get(api_url)
        data = response.json()
        return data.get("result", {}).get(pmid, {})

    def _verify_pmid(self, ref: dict) -> VerificationResult:
        """PubMed IDを検証"""
        pmid = ref["pmid"]
        detail = self._get_pubmed_detail(pmid)

        if detail and "error" not in detail:
            title = detail.get("title", "")
            return VerificationResult(
                reference_text=ref["context"],
                url=ref["url"],
                ref_type="PMID",
                status="valid",
                http_status=200,
                resolved_title=title,
            )
        else:
            return VerificationResult(
                reference_text=ref["context"],
                url=ref["url"],
                ref_type="PMID",
                status="invalid",
                error_message=f"PMID {pmid} が PubMed に存在しません",
            )

    def _verify_doi(self, ref: dict) -> VerificationResult:
        """DOIリンクを検証"""
        url = ref["url"]
        response = self.client.head(url)
        if response.status_code < 400:
            return VerificationResult(
                reference_text=ref["context"],
                url=url,
                ref_type="DOI",
                status="valid",
                http_status=response.status_code,
            )
        else:
            return VerificationResult(
                reference_text=ref["context"],
                url=url,
                ref_type="DOI",
                status="invalid",
                http_status=response.status_code,
                error_message=f"HTTP {response.status_code}",
            )

    def _verify_url(self, ref: dict) -> VerificationResult:
        """一般URLを検証"""
        url = ref["url"]
        try:
            response = self.client.head(url)
        except httpx.HTTPError:
            response = self.client.get(url)

        if response.status_code < 400:
            return VerificationResult(
                reference_text=ref["context"],
                url=url,
                ref_type="URL",
                status="valid",
                http_status=response.status_code,
            )
        else:
            return VerificationResult(
                reference_text=ref["context"],
                url=url,
                ref_type="URL",
                status="invalid",
                http_status=response.status_code,
                error_message=f"HTTP {response.status_code}",
            )

    def _get_context(self, text: str, pos: int) -> str:
        """URLの前後から文献のコンテキスト行を取得"""
        start = text.rfind("\n", 0, pos)
        end = text.find("\n", pos)
        if start == -1:
            start = 0
        if end == -1:
            end = len(text)
        line = text[start:end].strip()
        return line[:200] if len(line) > 200 else line

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
