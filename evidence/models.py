"""エビデンスデータのモデル定義"""

from dataclasses import dataclass, field
from enum import Enum


class EvidenceLevel(Enum):
    """エビデンスレベル（Oxford CEBM準拠）"""
    LEVEL_1A = "1a"  # SR of RCTs
    LEVEL_1B = "1b"  # Individual RCT
    LEVEL_2A = "2a"  # SR of cohort studies
    LEVEL_2B = "2b"  # Individual cohort study
    LEVEL_3A = "3a"  # SR of case-control studies
    LEVEL_3B = "3b"  # Individual case-control study
    LEVEL_4 = "4"    # Case series
    LEVEL_5 = "5"    # Expert opinion
    GUIDELINE = "guideline"  # 公的ガイドライン
    AUTHORITY = "authority"  # 公的機関の声明


class SourceType(Enum):
    """情報源の種類"""
    WHO = "WHO"
    ADA = "ADA"
    AAPD = "AAPD"
    MHLW = "厚生労働省"
    JSPD = "日本小児歯科学会"
    COCHRANE = "Cochrane"
    PUBMED = "PubMed"
    OTHER = "Other"


@dataclass
class Evidence:
    """個別エビデンス"""
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    journal: str = ""
    doi: str = ""
    pmid: str = ""
    abstract: str = ""
    evidence_level: EvidenceLevel = EvidenceLevel.LEVEL_5
    source_type: SourceType = SourceType.OTHER
    url: str = ""
    key_findings: str = ""
    summary_ja: str = ""  # 日本語要約

    @property
    def citation(self) -> str:
        """引用文字列を生成"""
        author_str = self.authors[0] + " et al." if len(self.authors) > 1 else (
            self.authors[0] if self.authors else "Unknown"
        )
        return f"{author_str} ({self.year}). {self.title}. {self.journal}"

    @property
    def priority(self) -> int:
        """エビデンスの優先度（低い数値ほど高優先）"""
        priority_map = {
            EvidenceLevel.AUTHORITY: 1,
            EvidenceLevel.GUIDELINE: 2,
            EvidenceLevel.LEVEL_1A: 3,
            EvidenceLevel.LEVEL_1B: 4,
            EvidenceLevel.LEVEL_2A: 5,
            EvidenceLevel.LEVEL_2B: 6,
            EvidenceLevel.LEVEL_3A: 7,
            EvidenceLevel.LEVEL_3B: 8,
            EvidenceLevel.LEVEL_4: 9,
            EvidenceLevel.LEVEL_5: 10,
        }
        return priority_map.get(self.evidence_level, 10)


@dataclass
class EvidenceCollection:
    """トピックに対するエビデンスのコレクション"""
    topic_id: str
    evidences: list[Evidence] = field(default_factory=list)

    def sorted_by_priority(self) -> list[Evidence]:
        """優先度順にソートしたエビデンスを返す"""
        return sorted(self.evidences, key=lambda e: (e.priority, -(e.year or 0)))

    def by_level(self, level: EvidenceLevel) -> list[Evidence]:
        """特定レベルのエビデンスを返す"""
        return [e for e in self.evidences if e.evidence_level == level]

    def has_high_quality(self) -> bool:
        """高品質エビデンス（SR/メタアナリシス/ガイドライン）があるか"""
        high_levels = {
            EvidenceLevel.AUTHORITY,
            EvidenceLevel.GUIDELINE,
            EvidenceLevel.LEVEL_1A,
            EvidenceLevel.LEVEL_1B,
        }
        return any(e.evidence_level in high_levels for e in self.evidences)

    @property
    def summary(self) -> str:
        """エビデンス概要"""
        total = len(self.evidences)
        sorted_ev = self.sorted_by_priority()
        best = sorted_ev[0].evidence_level.value if sorted_ev else "none"
        return f"Total: {total}, Best level: {best}"
