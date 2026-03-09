"""記事内リンク検証・修復サービス

記事生成後に自動実行し、参考文献リンクの到達確認・整合性チェック・修復を行う。

Protocol:
  1. 記事内のMarkdownリンク [text](url) を抽出
  2. 各URLに到達確認（HTTP HEAD / PubMed API）
  3. 無効リンク → PubMedタイトル検索で正しいURLを特定
  4. 整合性チェック: リンク先のタイトル・著者と記事内引用が一致するか
  5. 整合性NG → エビデンス再収集フラグを返す
"""

import logging
import re
import sys
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import httpx

_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logger = logging.getLogger(__name__)

# Markdownリンクパターン: [text](url)
MD_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\((https?://[^\)]+)\)')
# DOIパターン
DOI_PATTERN = re.compile(r'(10\.\d{4,}/[^\s\)"\]]+)')


@dataclass
class LinkCheckResult:
    """個別リンクの検証結果"""
    link_text: str
    url: str
    status: str  # "valid" | "invalid" | "fixed" | "inconsistent" | "timeout"
    http_status: int | None = None
    resolved_title: str = ""
    fixed_url: str = ""
    error_message: str = ""
    consistency_ok: bool = True


@dataclass
class ArticleLinkReport:
    """記事全体のリンク検証レポート"""
    results: list[LinkCheckResult] = field(default_factory=list)
    needs_re_research: bool = False
    fixed_article: str = ""

    @property
    def all_valid(self) -> bool:
        return all(r.status in ("valid", "fixed") for r in self.results)

    @property
    def invalid_count(self) -> int:
        return sum(1 for r in self.results if r.status not in ("valid", "fixed"))

    @property
    def fixed_count(self) -> int:
        return sum(1 for r in self.results if r.status == "fixed")


class LinkValidator:
    """記事内リンクの検証・修復"""

    def __init__(self, timeout: float = 15.0):
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "DentalArticleBot/1.0 (link validation)"},
        )

    def validate_and_fix(self, article_text: str) -> ArticleLinkReport:
        """記事内のリンクを検証し、無効なものは修復を試みる

        Returns:
            ArticleLinkReport: 検証結果。fixed_articleに修正済み記事テキストを格納。
        """
        report = ArticleLinkReport()
        links = self._extract_links(article_text)

        if not links:
            report.fixed_article = article_text
            return report

        fixed_text = article_text

        for link in links:
            result = self._check_link(link)

            if result.status == "invalid":
                # 修復を試みる
                result = self._try_fix(result)

            if result.status == "fixed" and result.fixed_url:
                # 記事内のURLを置換
                fixed_text = fixed_text.replace(
                    f"]({result.url})",
                    f"]({result.fixed_url})",
                )
                logger.info(f"Link fixed: {result.url} -> {result.fixed_url}")

            if result.status == "inconsistent":
                report.needs_re_research = True

            report.results.append(result)

        report.fixed_article = fixed_text
        return report

    def _extract_links(self, text: str) -> list[dict]:
        """記事からMarkdownリンクを抽出"""
        links = []
        seen = set()
        for match in MD_LINK_PATTERN.finditer(text):
            url = match.group(2).rstrip(".,;)")
            if url not in seen:
                links.append({
                    "text": match.group(1),
                    "url": url,
                })
                seen.add(url)
        return links

    def _check_link(self, link: dict) -> LinkCheckResult:
        """リンクの到達確認"""
        url = link["url"]
        text = link["text"]

        try:
            # PubMedリンクの場合はAPIで検証
            pmid_match = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', url)
            if pmid_match:
                return self._check_pubmed(link, pmid_match.group(1))

            # DOIリンクの場合
            if "doi.org/" in url:
                return self._check_doi(link)

            # 一般URL
            response = self.client.head(url)
            if response.status_code < 400:
                return LinkCheckResult(
                    link_text=text, url=url,
                    status="valid", http_status=response.status_code,
                )
            else:
                return LinkCheckResult(
                    link_text=text, url=url,
                    status="invalid", http_status=response.status_code,
                    error_message=f"HTTP {response.status_code}",
                )

        except httpx.TimeoutException:
            return LinkCheckResult(
                link_text=text, url=url,
                status="timeout", error_message="接続タイムアウト",
            )
        except Exception as e:
            return LinkCheckResult(
                link_text=text, url=url,
                status="invalid", error_message=str(e),
            )

    def _check_pubmed(self, link: dict, pmid: str) -> LinkCheckResult:
        """PubMedリンクをAPIで検証し、タイトル整合性もチェック"""
        detail = self._get_pubmed_detail(pmid)
        if not detail or "error" in detail:
            return LinkCheckResult(
                link_text=link["text"], url=link["url"],
                status="invalid",
                error_message=f"PMID {pmid} が PubMed に存在しません",
            )

        pubmed_title = detail.get("title", "")
        consistency = self._check_consistency(link["text"], pubmed_title, detail)

        return LinkCheckResult(
            link_text=link["text"], url=link["url"],
            status="valid" if consistency else "inconsistent",
            http_status=200,
            resolved_title=pubmed_title,
            consistency_ok=consistency,
            error_message="" if consistency else
                f"整合性エラー: 記事内「{link['text'][:60]}」とPubMedタイトル「{pubmed_title[:60]}」が不一致",
        )

    def _check_doi(self, link: dict) -> LinkCheckResult:
        """DOIリンクの到達確認"""
        url = link["url"]
        try:
            response = self.client.head(url)
            if response.status_code < 400:
                return LinkCheckResult(
                    link_text=link["text"], url=url,
                    status="valid", http_status=response.status_code,
                )
            else:
                return LinkCheckResult(
                    link_text=link["text"], url=url,
                    status="invalid", http_status=response.status_code,
                    error_message=f"HTTP {response.status_code}",
                )
        except httpx.TimeoutException:
            return LinkCheckResult(
                link_text=link["text"], url=url,
                status="timeout", error_message="DOI解決タイムアウト",
            )

    def _try_fix(self, result: LinkCheckResult) -> LinkCheckResult:
        """無効リンクの修復を試みる"""
        text = result.link_text

        # 引用テキストからタイトルを抽出して PubMed 検索
        # 典型的な引用: "著者 et al. タイトル. *ジャーナル.* 年;..."
        title_match = re.search(r'(?:et al\.\s*)?(.+?)[\.\*]', text)
        search_text = title_match.group(1).strip() if title_match else text[:80]

        # 著者名も抽出
        author_match = re.match(r'^([A-Za-z]+(?:\s[A-Z])?)', text)
        author = author_match.group(1) if author_match else ""

        query = search_text
        if author:
            query = f"{author} {search_text}"

        try:
            encoded = urllib.parse.quote(query[:100])
            search_url = (
                f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
                f"?db=pubmed&term={encoded}&retmode=json&retmax=3"
            )
            response = self.client.get(search_url)
            data = response.json()
            id_list = data.get("esearchresult", {}).get("idlist", [])

            if id_list:
                pmid = id_list[0]
                detail = self._get_pubmed_detail(pmid)
                pubmed_title = detail.get("title", "") if detail else ""
                new_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

                # 整合性チェック
                if self._check_consistency(text, pubmed_title, detail):
                    result.status = "fixed"
                    result.fixed_url = new_url
                    result.resolved_title = pubmed_title
                    result.error_message = f"リンク修復: {new_url}"
                    result.consistency_ok = True
                    logger.info(f"Link fixed via PubMed search: {text[:50]} -> PMID {pmid}")
                else:
                    result.status = "inconsistent"
                    result.consistency_ok = False
                    result.error_message = (
                        f"PubMed検索でPMID {pmid}が見つかりましたが、"
                        f"記事の記述と整合しません。エビデンスの再収集が必要です。"
                    )
            else:
                result.error_message = f"PubMedで該当文献が見つかりませんでした: {search_text[:50]}"

        except Exception as e:
            result.error_message = f"リンク修復エラー: {e}"

        return result

    def _check_consistency(self, citation_text: str, pubmed_title: str,
                          detail: dict | None) -> bool:
        """引用テキストとPubMedの論文情報の整合性をチェック"""
        if not pubmed_title or not detail:
            return False

        citation_lower = citation_text.lower()
        pubmed_lower = pubmed_title.lower()

        # 1. タイトルの部分一致（最初の30文字程度）
        # PubMedタイトルの最初の単語をいくつか引用テキストに含むか
        title_words = [w for w in pubmed_lower.split()[:5]
                      if len(w) > 3 and w not in {"the", "and", "for", "with", "from"}]
        title_match = sum(1 for w in title_words if w in citation_lower)
        if title_match >= 2:
            return True

        # 2. 著者名の一致
        authors = detail.get("authors", [])
        if authors:
            first_author = authors[0].get("name", "").split()[0].lower() if isinstance(authors[0], dict) else ""
            if first_author and first_author in citation_lower:
                return True

        # 3. 年の一致
        pub_date = detail.get("pubdate", "")
        year_match = re.search(r'(\d{4})', pub_date)
        if year_match and year_match.group(1) in citation_text:
            return True

        # 4. ジャーナル名の一致
        source = detail.get("source", "").lower()
        if source and len(source) > 3 and source in citation_lower:
            return True

        return False

    def _get_pubmed_detail(self, pmid: str) -> dict | None:
        """PubMed IDの詳細情報を取得"""
        try:
            api_url = (
                f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                f"?db=pubmed&id={pmid}&retmode=json"
            )
            response = self.client.get(api_url)
            data = response.json()
            return data.get("result", {}).get(pmid)
        except Exception:
            return None

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
