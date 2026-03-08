"""公的機関のエビデンス取得モジュール（WHO, ADA, 厚労省等）"""

import logging

import httpx

from .models import Evidence, EvidenceLevel, SourceType

logger = logging.getLogger(__name__)


class WebEvidenceSearcher:
    """Web検索ベースの公的機関エビデンス収集

    Google Custom Search APIやスクレイピングではなく、
    各機関の公開APIやRSSフィード、既知のURLパターンを使用する。
    将来的にはClaude APIでウェブ検索を行うことも可能。
    """

    def __init__(self):
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)

    def search_who(self, keywords: list[str]) -> list[Evidence]:
        """WHO公式情報を検索

        WHOのAPIは限定的なため、既知のガイドライン・ファクトシートを
        キーワードで照合するアプローチを取る。
        """
        # WHO既知のエビデンス（歯科関連）
        who_sources = [
            Evidence(
                title="WHO guideline: use of fluorides for caries prevention",
                authors=["World Health Organization"],
                year=2023,
                evidence_level=EvidenceLevel.AUTHORITY,
                source_type=SourceType.WHO,
                url="https://www.who.int/publications/i/item/9789240096882",
                key_findings=(
                    "WHO recommends fluoride toothpaste (1000-1500 ppm) for all ages. "
                    "For children under 6, use a small amount (pea-sized or rice-grain)."
                ),
                summary_ja=(
                    "WHOは全年齢でフッ素配合歯磨き粉（1000-1500ppm）を推奨。"
                    "6歳未満は少量（豆粒大または米粒大）を使用。"
                ),
            ),
            Evidence(
                title="Sugars and dental caries (WHO Technical Information Note)",
                authors=["World Health Organization"],
                year=2017,
                evidence_level=EvidenceLevel.AUTHORITY,
                source_type=SourceType.WHO,
                url="https://www.who.int/news-room/fact-sheets/detail/sugars-and-dental-caries",
                key_findings=(
                    "Free sugars are the primary cause of dental caries. "
                    "WHO recommends limiting free sugar intake to less than 10% of total energy."
                ),
                summary_ja=(
                    "遊離糖類がむし歯の主要原因。WHOは遊離糖類の摂取を"
                    "総エネルギーの10%未満に抑えることを推奨。"
                ),
            ),
            Evidence(
                title="Ending childhood dental caries: WHO implementation manual",
                authors=["World Health Organization"],
                year=2019,
                evidence_level=EvidenceLevel.AUTHORITY,
                source_type=SourceType.WHO,
                url="https://www.who.int/publications/i/item/ending-childhood-dental-caries-who-implementation-manual",
                key_findings=(
                    "Comprehensive approach to childhood caries prevention including "
                    "fluoride use, sugar reduction, and regular dental visits."
                ),
                summary_ja=(
                    "小児むし歯予防の包括的アプローチ：フッ素使用、糖質制限、"
                    "定期歯科受診を推奨。"
                ),
            ),
        ]

        return self._filter_by_keywords(who_sources, keywords)

    def search_ada(self, keywords: list[str]) -> list[Evidence]:
        """ADA（米国歯科医師会）のエビデンスを検索"""
        ada_sources = [
            Evidence(
                title="ADA Clinical Practice Guideline: Topical Fluoride for Caries Prevention",
                authors=["American Dental Association"],
                year=2024,
                evidence_level=EvidenceLevel.GUIDELINE,
                source_type=SourceType.ADA,
                url="https://www.ada.org/resources/research/science-and-research-institute/evidence-based-dental-research/fluoride-topical-and-systemic-supplements",
                key_findings=(
                    "Professional fluoride varnish application every 3-6 months is recommended "
                    "for children at elevated caries risk."
                ),
                summary_ja=(
                    "むし歯リスクの高い小児には3〜6ヶ月ごとの"
                    "フッ素バーニッシュ塗布を推奨。"
                ),
            ),
            Evidence(
                title="ADA Policy: Use of Pit-and-Fissure Sealants",
                authors=["American Dental Association"],
                year=2023,
                evidence_level=EvidenceLevel.GUIDELINE,
                source_type=SourceType.ADA,
                url="https://www.ada.org/resources/research/science-and-research-institute/evidence-based-dental-research/dental-sealants",
                key_findings=(
                    "Dental sealants reduce caries by up to 80% in the first 2 years "
                    "and continue to be effective for up to 9 years."
                ),
                summary_ja=(
                    "シーラントは最初の2年間でむし歯を最大80%減少させ、"
                    "最大9年間効果が持続。"
                ),
            ),
            Evidence(
                title="ADA Guideline: First Dental Visit",
                authors=["American Dental Association"],
                year=2022,
                evidence_level=EvidenceLevel.GUIDELINE,
                source_type=SourceType.ADA,
                url="https://www.ada.org/resources/research/science-and-research-institute/evidence-based-dental-research",
                key_findings=(
                    "ADA recommends a child's first dental visit by age 1 or within "
                    "6 months of the first tooth eruption."
                ),
                summary_ja="ADAは1歳まで、または最初の歯が生えてから6ヶ月以内の初回受診を推奨。",
            ),
        ]

        return self._filter_by_keywords(ada_sources, keywords)

    def search_aapd(self, keywords: list[str]) -> list[Evidence]:
        """AAPD（米国小児歯科学会）のエビデンスを検索"""
        aapd_sources = [
            Evidence(
                title="AAPD Guideline: Fluoride Therapy",
                authors=["American Academy of Pediatric Dentistry"],
                year=2023,
                evidence_level=EvidenceLevel.GUIDELINE,
                source_type=SourceType.AAPD,
                url="https://www.aapd.org/research/oral-health-policies--recommendations/fluoride-therapy/",
                key_findings=(
                    "AAPD recommends fluoride varnish every 3-6 months starting at tooth eruption. "
                    "Fluoride toothpaste (smear for <3y, pea-size for 3-6y)."
                ),
                summary_ja=(
                    "歯が生えたらフッ素バーニッシュを3〜6ヶ月ごとに塗布。"
                    "歯磨き粉は3歳未満は米粒大、3〜6歳は豆粒大。"
                ),
            ),
            Evidence(
                title="AAPD Policy: Thumb, Finger, and Pacifier Habits",
                authors=["American Academy of Pediatric Dentistry"],
                year=2023,
                evidence_level=EvidenceLevel.GUIDELINE,
                source_type=SourceType.AAPD,
                url="https://www.aapd.org/research/oral-health-policies--recommendations/",
                key_findings=(
                    "Non-nutritive sucking is normal in infants. Most children stop by age 4. "
                    "Intervention should be considered if the habit persists beyond age 3."
                ),
                summary_ja=(
                    "非栄養性吸啜は乳児期には正常。多くは4歳までにやめる。"
                    "3歳を超えて続く場合は介入を検討。"
                ),
            ),
            Evidence(
                title="AAPD Guideline: Behavior Guidance for the Pediatric Dental Patient",
                authors=["American Academy of Pediatric Dentistry"],
                year=2023,
                evidence_level=EvidenceLevel.GUIDELINE,
                source_type=SourceType.AAPD,
                url="https://www.aapd.org/research/oral-health-policies--recommendations/behavior-guidance/",
                key_findings=(
                    "Tell-show-do, positive reinforcement, and distraction are recommended as "
                    "first-line behavior guidance techniques."
                ),
                summary_ja=(
                    "Tell-Show-Do法、ポジティブ強化、注意転換が"
                    "第一選択の行動管理テクニックとして推奨。"
                ),
            ),
        ]

        return self._filter_by_keywords(aapd_sources, keywords)

    def search_mhlw(self, keywords: list[str]) -> list[Evidence]:
        """厚生労働省のエビデンスを検索"""
        mhlw_sources = [
            Evidence(
                title="フッ化物洗口ガイドライン",
                authors=["厚生労働省"],
                year=2003,
                evidence_level=EvidenceLevel.AUTHORITY,
                source_type=SourceType.MHLW,
                url="https://www.mhlw.go.jp/topics/2003/07/tp0711-1.html",
                key_findings="フッ化物洗口の安全性と有効性を示すガイドライン。4歳以上で推奨。",
                summary_ja="フッ化物洗口は安全で有効。4歳以上で実施可能。",
            ),
            Evidence(
                title="日本人の食事摂取基準（2020年版）- カルシウム",
                authors=["厚生労働省"],
                year=2020,
                evidence_level=EvidenceLevel.AUTHORITY,
                source_type=SourceType.MHLW,
                url="https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/kenkou/eiyou/syokuji_kijyun.html",
                key_findings=(
                    "妊婦のカルシウム推奨量は成人女性と同じ（650mg/日）。"
                    "妊娠中はカルシウム吸収率が上昇するため付加量なし。"
                ),
                summary_ja=(
                    "妊婦のカルシウム推奨量は650mg/日。"
                    "妊娠中は吸収率が上がるため追加量は不要。"
                ),
            ),
        ]

        return self._filter_by_keywords(mhlw_sources, keywords)

    def _filter_by_keywords(
        self, sources: list[Evidence], keywords: list[str]
    ) -> list[Evidence]:
        """キーワードに基づいてエビデンスをフィルタリング"""
        if not keywords:
            return sources

        matched: list[Evidence] = []
        keywords_lower = [kw.lower() for kw in keywords]

        for source in sources:
            searchable = (
                f"{source.title} {source.key_findings} {source.summary_ja} "
                f"{' '.join(source.authors)}"
            ).lower()

            if any(kw in searchable for kw in keywords_lower):
                matched.append(source)

        return matched

    def search_all(self, keywords: list[str]) -> list[Evidence]:
        """全ての公的機関から一括検索"""
        results: list[Evidence] = []
        results.extend(self.search_who(keywords))
        results.extend(self.search_ada(keywords))
        results.extend(self.search_aapd(keywords))
        results.extend(self.search_mhlw(keywords))
        return results

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
