"""記事品質チェッカー"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    """品質チェックレポート"""
    topic_id: str
    word_count: int = 0
    has_references: bool = False
    reference_count: int = 0
    has_cta: bool = False
    compliance_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    score: float = 0.0  # 0-100

    @property
    def passed(self) -> bool:
        return self.score >= 60 and len(self.compliance_issues) == 0

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"Quality Report [{status}] - Score: {self.score:.0f}/100",
            f"  Word count: {self.word_count}",
            f"  References: {self.reference_count}",
            f"  CTA: {'Yes' if self.has_cta else 'No'}",
        ]
        if self.compliance_issues:
            lines.append(f"  Compliance issues: {len(self.compliance_issues)}")
            for issue in self.compliance_issues:
                lines.append(f"    - {issue}")
        if self.warnings:
            lines.append(f"  Warnings: {len(self.warnings)}")
            for warning in self.warnings:
                lines.append(f"    - {warning}")
        return "\n".join(lines)


class QualityChecker:
    """記事の品質をチェック"""

    # 医療広告ガイラインで避けるべき表現
    PROHIBITED_PHRASES = [
        "絶対に治る",
        "100%",
        "必ず治ります",
        "最高の",
        "日本一",
        "世界一",
        "他院より優れ",
        "副作用はありません",
        "リスクはゼロ",
        "痛みはありません",
        "確実に",
    ]

    # 過度な恐怖訴求の表現
    FEAR_PHRASES = [
        "取り返しのつかない",
        "手遅れになる",
        "一生後悔",
        "今すぐしないと",
        "絶対に放置しないで",
    ]

    def check(
        self, article_text: str, topic_id: str, is_public: bool = False
    ) -> QualityReport:
        """記事の品質チェックを実行

        Args:
            article_text: チェック対象の記事テキスト
            topic_id: トピックID
            is_public: 一般公開版の場合True（文字数基準が異なる）
        """
        report = QualityReport(topic_id=topic_id)

        # 公開版かどうかの自動検出（topic_idに_publicが含まれる場合も公開版扱い）
        if topic_id.endswith("_public"):
            is_public = True

        # 1. 文字数チェック（公開版は基準が異なる）
        report.word_count = len(article_text)
        if is_public:
            if report.word_count < 2000:
                report.warnings.append(
                    f"文字数が少ない ({report.word_count}文字、公開版推奨3000以上)"
                )
            elif report.word_count > 10000:
                report.warnings.append(
                    f"文字数が多い ({report.word_count}文字、公開版推奨6000以下)"
                )
        else:
            if report.word_count < 1000:
                report.warnings.append(
                    f"文字数が少ない ({report.word_count}文字、推奨1500以上)"
                )
            elif report.word_count > 5000:
                report.warnings.append(
                    f"文字数が多い ({report.word_count}文字、推奨3000以下)"
                )

        # 2. 参考文献チェック
        report.has_references = bool(
            re.search(r"(参考文献|出典|References|引用|参照)", article_text)
        )
        # URL形式の参照をカウント
        urls = re.findall(r"https?://\S+", article_text)
        report.reference_count = len(urls)
        if report.reference_count == 0:
            report.warnings.append("参考文献のURLが含まれていません")

        # 3. CTA（相談誘導）チェック
        cta_patterns = ["ご相談", "お気軽に", "当院", "受診", "ご予約"]
        report.has_cta = any(p in article_text for p in cta_patterns)
        if not report.has_cta:
            report.warnings.append("CTAが含まれていません")

        # 4. 医療広告ガイドライン準拠チェック
        for phrase in self.PROHIBITED_PHRASES:
            if phrase in article_text:
                report.compliance_issues.append(
                    f"医療広告GL違反の可能性: 「{phrase}」"
                )

        # 5. 恐怖訴求チェック
        for phrase in self.FEAR_PHRASES:
            if phrase in article_text:
                report.compliance_issues.append(
                    f"過度な恐怖訴求: 「{phrase}」"
                )

        # 6. 構成チェック
        has_heading = bool(re.search(r"^#+\s", article_text, re.MULTILINE))
        if not has_heading:
            report.warnings.append("見出し（#）が含まれていません")

        # スコア算出
        report.score = self._calculate_score(report)

        return report

    def _calculate_score(self, report: QualityReport) -> float:
        """品質スコアを算出（100点満点）"""
        score = 100.0

        # 文字数
        if report.word_count < 1000:
            score -= 20
        elif report.word_count < 1500:
            score -= 10

        if report.word_count > 5000:
            score -= 10

        # 参考文献
        if not report.has_references:
            score -= 15
        if report.reference_count == 0:
            score -= 15
        elif report.reference_count < 3:
            score -= 5

        # CTA
        if not report.has_cta:
            score -= 10

        # コンプライアンス（致命的）
        score -= len(report.compliance_issues) * 20

        # 警告
        score -= len(report.warnings) * 3

        return max(0, min(100, score))
