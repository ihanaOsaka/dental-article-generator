"""PubMed検索モジュール - NCBI E-utilities API経由"""

import json
import logging
import time
from xml.etree import ElementTree

import httpx

from .models import Evidence, EvidenceLevel, SourceType

logger = logging.getLogger(__name__)

# PubMedの論文タイプとエビデンスレベルのマッピング
PUBLICATION_TYPE_LEVEL = {
    "Meta-Analysis": EvidenceLevel.LEVEL_1A,
    "Systematic Review": EvidenceLevel.LEVEL_1A,
    "Randomized Controlled Trial": EvidenceLevel.LEVEL_1B,
    "Clinical Trial": EvidenceLevel.LEVEL_2B,
    "Observational Study": EvidenceLevel.LEVEL_2B,
    "Review": EvidenceLevel.LEVEL_5,
    "Practice Guideline": EvidenceLevel.GUIDELINE,
    "Guideline": EvidenceLevel.GUIDELINE,
}


class PubMedSearcher:
    """PubMed E-utilities APIを使用した文献検索"""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, api_key: str = "", max_results: int = 20, date_range_years: int = 10):
        self.api_key = api_key
        self.max_results = max_results
        self.date_range_years = date_range_years
        self.client = httpx.Client(timeout=30.0)

    def search(self, query: str, filters: list[str] | None = None) -> list[Evidence]:
        """PubMedを検索してエビデンスリストを返す"""
        pmids = self._esearch(query, filters)
        if not pmids:
            logger.info(f"No results found for query: {query}")
            return []

        articles = self._efetch(pmids)
        return articles

    def search_for_topic(
        self,
        search_terms: list[str],
        filters: list[str] | None = None,
    ) -> list[Evidence]:
        """トピックの検索語リストからエビデンスを収集"""
        all_evidences: list[Evidence] = []
        seen_pmids: set[str] = set()

        # 各検索語でOR結合して一括検索
        combined_query = " OR ".join(f"({term})" for term in search_terms)

        evidences = self.search(combined_query, filters)
        for ev in evidences:
            if ev.pmid not in seen_pmids:
                seen_pmids.add(ev.pmid)
                all_evidences.append(ev)

        return all_evidences

    def _esearch(self, query: str, filters: list[str] | None = None) -> list[str]:
        """ESearch APIでPMIDリストを取得"""
        # フィルターを追加
        search_query = query
        if filters:
            filter_str = " OR ".join(f'"{f}"[pt]' for f in filters)
            search_query = f"({query}) AND ({filter_str})"

        # 日付範囲を追加
        if self.date_range_years:
            search_query += f' AND ("last {self.date_range_years} years"[PDat])'

        params = {
            "db": "pubmed",
            "term": search_query,
            "retmax": self.max_results,
            "sort": "relevance",
            "retmode": "json",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        logger.info(f"PubMed search: {search_query}")

        try:
            resp = self.client.get(f"{self.BASE_URL}/esearch.fcgi", params=params)
            resp.raise_for_status()
            data = resp.json()
            pmids = data.get("esearchresult", {}).get("idlist", [])
            logger.info(f"Found {len(pmids)} results")
            return pmids
        except Exception as e:
            logger.error(f"ESearch failed: {e}")
            return []

    def _efetch(self, pmids: list[str]) -> list[Evidence]:
        """EFetch APIで論文詳細を取得"""
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            resp = self.client.get(f"{self.BASE_URL}/efetch.fcgi", params=params)
            resp.raise_for_status()
            return self._parse_xml(resp.text)
        except Exception as e:
            logger.error(f"EFetch failed: {e}")
            return []

    def _parse_xml(self, xml_text: str) -> list[Evidence]:
        """PubMed XMLレスポンスをパースしてEvidenceリストに変換"""
        evidences: list[Evidence] = []

        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.error(f"XML parse error: {e}")
            return []

        for article in root.findall(".//PubmedArticle"):
            try:
                ev = self._parse_article(article)
                if ev:
                    evidences.append(ev)
            except Exception as e:
                logger.warning(f"Failed to parse article: {e}")

        return evidences

    def _parse_article(self, article: ElementTree.Element) -> Evidence | None:
        """個別論文をパース"""
        medline = article.find(".//MedlineCitation")
        if medline is None:
            return None

        # PMID
        pmid_elem = medline.find("PMID")
        pmid = pmid_elem.text if pmid_elem is not None else ""

        # タイトル
        title_elem = medline.find(".//ArticleTitle")
        title = title_elem.text if title_elem is not None else "Untitled"

        # 著者
        authors: list[str] = []
        for author in medline.findall(".//Author"):
            lastname = author.find("LastName")
            forename = author.find("ForeName")
            if lastname is not None:
                name = lastname.text or ""
                if forename is not None and forename.text:
                    name += f" {forename.text}"
                authors.append(name)

        # 出版年
        year = None
        year_elem = medline.find(".//PubDate/Year")
        if year_elem is not None and year_elem.text:
            try:
                year = int(year_elem.text)
            except ValueError:
                pass

        # ジャーナル
        journal_elem = medline.find(".//Journal/Title")
        journal = journal_elem.text if journal_elem is not None else ""

        # DOI
        doi = ""
        for id_elem in article.findall(".//ArticleId"):
            if id_elem.get("IdType") == "doi":
                doi = id_elem.text or ""
                break

        # 抄録
        abstract_parts: list[str] = []
        for abstract_text in medline.findall(".//Abstract/AbstractText"):
            label = abstract_text.get("Label", "")
            text = abstract_text.text or ""
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
        abstract = " ".join(abstract_parts)

        # 論文タイプからエビデンスレベルを推定
        evidence_level = EvidenceLevel.LEVEL_5
        for pub_type in medline.findall(".//PublicationType"):
            pub_type_text = pub_type.text or ""
            if pub_type_text in PUBLICATION_TYPE_LEVEL:
                candidate = PUBLICATION_TYPE_LEVEL[pub_type_text]
                # より高いレベルを採用
                if candidate.value < evidence_level.value or evidence_level == EvidenceLevel.LEVEL_5:
                    evidence_level = candidate

        return Evidence(
            title=title,
            authors=authors,
            year=year,
            journal=journal,
            doi=doi,
            pmid=pmid,
            abstract=abstract,
            evidence_level=evidence_level,
            source_type=SourceType.PUBMED,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
        )

    def close(self):
        """HTTPクライアントを閉じる"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
