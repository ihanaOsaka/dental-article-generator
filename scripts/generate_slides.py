#!/usr/bin/env python3
"""Generate slide files from video scenario markdown files."""

import re
import os
from pathlib import Path

SCENARIOS_DIR = Path("output/video_scenarios")
SLIDES_DIR = Path("output/slides")


def parse_scenario(filepath: Path) -> dict:
    """Parse a video scenario markdown file into structured data."""
    text = filepath.read_text(encoding="utf-8")

    # Extract title
    title_match = re.search(r"^# 動画シナリオ #(\d+)：(.+)$", text, re.MULTILINE)
    number = title_match.group(1)
    title = title_match.group(2)

    # Extract target audience
    audience_match = re.search(r"\| 対象視聴者 \| (.+?) \|", text)
    audience = audience_match.group(1) if audience_match else ""

    # Extract key message
    key_msg_match = re.search(r"\*\*キーメッセージ:\*\* (.+?)$", text, re.MULTILINE)
    key_message = key_msg_match.group(1).strip().strip("「」") if key_msg_match else ""

    # Extract sections
    sections = []
    # Split by ### headers
    section_pattern = re.compile(
        r"### (.+?)(?:\n\n|\n)"
        r"(.*?)(?=\n### |\n## 制作メモ|\Z)",
        re.DOTALL,
    )
    for match in section_pattern.finditer(text):
        header = match.group(1).strip()
        body = match.group(2).strip()

        # Extract テロップ
        telop_match = re.search(r"\*\*テロップ:\*\* (.+?)$", body, re.MULTILINE)
        telop = telop_match.group(1).strip() if telop_match else ""

        # Extract narration
        narration = ""
        nar_match = re.search(
            r"\*\*ナレーション:\*\*\n(.+?)(?=\n\*\*|$)", body, re.DOTALL
        )
        if nar_match:
            narration = nar_match.group(1).strip()
            # Clean up narration - remove quotes
            narration = re.sub(r"^「|」$", "", narration.strip())

        # Extract question if present
        question = ""
        q_match = re.search(
            r"\*\*質問（画面テキスト\+読み上げ）:\*\*\n(.+?)(?=\n\*\*|$)",
            body,
            re.DOTALL,
        )
        if q_match:
            question = q_match.group(1).strip()
            question = re.sub(r"^「|」$", "", question.strip())

        # Extract visual notes
        visual = ""
        vis_match = re.search(
            r"\*\*画面演出案:\*\*\n(.+?)(?=\n---|\Z)", body, re.DOTALL
        )
        if vis_match:
            visual = vis_match.group(1).strip()

        sections.append(
            {
                "header": header,
                "telop": telop,
                "narration": narration,
                "question": question,
                "visual": visual,
            }
        )

    return {
        "number": number,
        "title": title,
        "audience": audience,
        "key_message": key_message,
        "sections": sections,
    }


def extract_narration_bullets(narration: str) -> list[str]:
    """Extract key points from narration as bullet points."""
    bullets = []
    lines = narration.split("\n")
    current = []
    for line in lines:
        line = line.strip().strip("「」")
        if not line:
            if current:
                bullets.append("".join(current))
                current = []
        else:
            current.append(line)
    if current:
        bullets.append("".join(current))

    # Keep only substantive bullets (skip very short connectors)
    return [b for b in bullets if len(b) > 5]


def generate_slide_md(scenario: dict) -> str:
    """Generate a slide markdown file from parsed scenario data."""
    num = scenario["number"]
    title = scenario["title"]
    audience = scenario["audience"]
    key_message = scenario["key_message"]
    sections = scenario["sections"]

    lines = []
    lines.append(f"# スライド #{num}：{title}\n")
    lines.append(f"**対象:** {audience}\n")
    lines.append("---\n")

    slide_num = 1

    for sec in sections:
        header = sec["header"]
        telop = sec["telop"]
        narration = sec["narration"]
        question = sec["question"]
        visual = sec["visual"]

        # Determine slide type
        is_opening = "オープニング" in header
        is_ending = "エンディング" in header

        lines.append(f"## スライド {slide_num}：{header}\n")

        if telop:
            lines.append(f"### 📌 {telop}\n")

        if is_opening and question:
            lines.append("**視聴者の質問:**\n")
            lines.append(f"> {question}\n")
        elif narration:
            bullets = extract_narration_bullets(narration)
            if bullets:
                lines.append("**ポイント:**\n")
                for b in bullets:
                    lines.append(f"- {b}")
                lines.append("")

        if visual:
            lines.append(f"**ビジュアル:**\n{visual}\n")

        lines.append("---\n")
        slide_num += 1

    # Summary slide
    lines.append(f"## スライド {slide_num}：まとめ\n")
    if key_message:
        lines.append(f"**キーメッセージ:** {key_message}\n")
    lines.append("**お問い合わせ:** クリニック情報・予約方法\n")

    return "\n".join(lines)


def main():
    SLIDES_DIR.mkdir(parents=True, exist_ok=True)

    scenario_files = sorted(SCENARIOS_DIR.glob("*.md"))
    print(f"Found {len(scenario_files)} scenarios")

    for filepath in scenario_files:
        scenario = parse_scenario(filepath)
        slide_md = generate_slide_md(scenario)

        output_path = SLIDES_DIR / filepath.name
        output_path.write_text(slide_md, encoding="utf-8")
        print(f"  Generated: {output_path.name}")

    print(f"\nDone! {len(scenario_files)} slide files created in {SLIDES_DIR}/")


if __name__ == "__main__":
    main()
