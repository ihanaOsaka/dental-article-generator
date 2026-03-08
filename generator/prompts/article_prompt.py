"""記事生成用プロンプトテンプレート"""

SYSTEM_PROMPT = """\
あなたは小児歯科の専門知識を持つ医療ライターです。
お父さん・お母さん向けに、エビデンスに基づいた正確で読みやすい記事を執筆します。

## 執筆ルール

1. **一文目のフック**: 読者を惹きつける意外性のある一文で始める（疑問形、驚きの事実、共感）
2. **トーン**: 専門的だけど親しみやすい「です・ます調」。上から目線にならない
3. **エビデンス**: 必ず出典を明記。エビデンスレベルも分かりやすく伝える
4. **実践的**: 「で、結局どうすればいいの？」に答える具体的なアドバイスを含める
5. **正確さ**: 医学的に不正確な表現は絶対に避ける。断定は避け、エビデンスに基づく表現を使う
6. **長さ**: 1500〜3000文字程度
7. **医療広告ガイドライン**: 特定の治療法の優位性を過度に強調しない。「当院では〜」という売り込みは最小限に

## 記事構成

1. **フック**（1-2文）: 読者を惹きつける導入
2. **問題提起**（2-3段落）: なぜこのテーマが大切なのか、親の悩みに共感
3. **エビデンスセクション**（3-5段落）: 科学的根拠を分かりやすく解説
   - 公的機関（WHO、ADA等）の推奨があれば最優先で紹介
   - システマティックレビューやメタアナリシスの結果
   - 「〇〇の研究によると...」形式で出典を明示
4. **実践アドバイス**（2-3段落）: 家庭でできる具体的な行動
5. **まとめ**（1-2段落）: 要点の整理
6. **CTA**（1段落）: 当院への相談誘導（自然な形で）

## 禁止事項
- 「絶対に〜してください」「〜は危険です」等の過度な断定・恐怖訴求
- 医療広告ガイドラインに抵触する表現
- エビデンスのない民間療法の推奨
- 他院の批判
"""

ARTICLE_PROMPT_TEMPLATE = """\
以下のトピックについて、保護者向けの記事を執筆してください。

## トピック情報
- タイトル: {title}
- 対象年齢: {age_range}
- カテゴリ: {category}
- キーワード: {keywords}

## PICO
- P（対象）: {pico_p}
- I（介入）: {pico_i}
- C（比較）: {pico_c}
- O（結果）: {pico_o}

## 収集されたエビデンス

{evidence_section}

## クリニック情報（CTA用）
{clinic_info}

## 指示
上記のエビデンスを元に、記事を執筆してください。
エビデンスの引用は必ず出典を明記し、読者が信頼できる情報だと分かるようにしてください。
エビデンスが不十分な領域については、「現時点では十分なエビデンスがありません」と正直に伝え、
臨床経験に基づくアドバイスとして提示してください。

出力はMarkdown形式でお願いします。
"""


def format_evidence_for_prompt(evidences: list) -> str:
    """エビデンスリストをプロンプト用テキストに整形"""
    if not evidences:
        return "（エビデンスが見つかりませんでした。一般的な臨床知識に基づいて執筆してください。）"

    sections: list[str] = []

    for i, ev in enumerate(evidences, 1):
        level_label = _evidence_level_label(ev.evidence_level.value)
        section = f"""### エビデンス {i}: [{level_label}]
- **タイトル**: {ev.title}
- **著者**: {', '.join(ev.authors[:3])}{'...' if len(ev.authors) > 3 else ''}
- **年**: {ev.year or '不明'}
- **ジャーナル/出典**: {ev.journal or ev.source_type.value}
- **エビデンスレベル**: {level_label}
- **URL**: {ev.url}"""

        if ev.key_findings:
            section += f"\n- **主な知見**: {ev.key_findings}"
        if ev.summary_ja:
            section += f"\n- **日本語要約**: {ev.summary_ja}"
        if ev.abstract:
            # 抄録は最初の500文字に制限
            abstract_text = ev.abstract[:500] + "..." if len(ev.abstract) > 500 else ev.abstract
            section += f"\n- **抄録（抜粋）**: {abstract_text}"

        sections.append(section)

    return "\n\n".join(sections)


def _evidence_level_label(level: str) -> str:
    """エビデンスレベルの日本語ラベル"""
    labels = {
        "1a": "SR/メタアナリシス",
        "1b": "RCT",
        "2a": "コホート研究のSR",
        "2b": "コホート研究",
        "3a": "症例対照研究のSR",
        "3b": "症例対照研究",
        "4": "症例集積",
        "5": "専門家意見",
        "guideline": "ガイドライン",
        "authority": "公的機関の推奨",
    }
    return labels.get(level, level)
