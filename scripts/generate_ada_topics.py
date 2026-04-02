"""ADAトピックCSVの「未作成」記事を順次生成するスクリプト"""

import csv
import json
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 生成対象のテーマ説明（ADAトピック → 日本語の記事テーマ）
TOPIC_PROMPTS = {
    "Aging and Dental Health": "高齢者の歯と口の健康管理。加齢による口腔内の変化、歯周病・根面う蝕のリスク、義歯のケア、ドライマウスとの関連。",
    "Amalgam": "歯科用アマルガム（銀歯）の安全性について。水銀含有への懸念、ADAやFDAの見解、代替材料との比較。",
    "Anesthesia and Sedation": "歯科治療での麻酔と鎮静法。局所麻酔の種類、笑気麻酔、静脈内鎮静法の安全性と適応。歯科恐怖症の方への対応。",
    "Antibiotic Prophylaxis Prior to Dental Procedures": "歯科治療前の抗菌薬予防投与。心疾患や人工関節を持つ患者への必要性、AHAガイドラインの最新情報。",
    "Bisphenol A": "歯科材料に含まれるビスフェノールA（BPA）の安全性。シーラントやコンポジットレジンからの溶出量、健康リスク、ADAの見解。",
    "Cancer (Head and Neck)": "頭頸部がんと口腔の健康。口腔がんの早期発見、リスク要因（喫煙・飲酒・HPV）、セルフチェック方法、定期歯科検診の重要性。",
    "Cancer Therapies and Dental Considerations": "がん治療中の口腔ケア。化学療法・放射線治療による口腔合併症（粘膜炎・ドライマウス・感染症）への対処法。",
    "Cannabis: Oral Health Effects": "大麻・マリファナの口腔健康への影響。ドライマウス、歯周病リスク、口腔がんとの関連についてのエビデンス。",
    "Celiac Disease": "セリアック病と口腔症状。エナメル質形成不全、口内炎、舌炎などの口腔内サイン。歯科での早期発見の重要性。",
    "Dental Floss/Interdental Cleaners": "デンタルフロスと歯間ブラシの正しい使い方。歯間清掃の重要性、種類と選び方、エビデンスに基づく効果。",
    "Denture Care and Maintenance": "入れ歯のお手入れと管理。毎日の清掃方法、洗浄剤の選び方、定期的な調整の重要性、入れ歯による口内炎の予防。",
    "Diabetes": "糖尿病と歯周病の関係。双方向の影響、血糖コントロールと口腔健康、糖尿病患者の歯科受診時の注意点。",
    "Genetics and Oral Health": "遺伝と口腔の健康。むし歯や歯周病のなりやすさと遺伝的要因、先天性歯科疾患について。",
    "Hypertension": "高血圧と歯科治療。降圧薬の口腔への副作用（歯肉増殖・ドライマウス）、歯科治療時の血圧管理。",
    "Methamphetamine": "メタンフェタミン（覚醒剤）の口腔への影響。いわゆる「メスマウス」の特徴、重度のむし歯と歯の崩壊。",
    "Mouthrinse (Mouthwash)": "マウスウォッシュ・洗口液の種類と効果。フッ化物配合・殺菌性洗口液の使い分け、アルコール含有の是非、ADAシール製品。",
    "Nitrous Oxide": "笑気麻酔（亜酸化窒素）の安全性と効果。歯科での使用方法、適応と禁忌、副作用、子どもへの使用。",
    "Oral Analgesics for Acute Dental Pain": "歯の急性痛に対する鎮痛薬。イブプロフェンとアセトアミノフェンの使い分け、オピオイド処方の現状と問題点。",
    "Oral Piercing/Jewelry": "口腔ピアス（舌・唇ピアス）のリスク。歯の欠け・歯肉退縮・感染症・神経損傷などの合併症。",
    "Oral-Systemic Health": "口腔と全身の健康の関係。歯周病と心血管疾患・糖尿病・肺炎・早産との関連についてのエビデンス。",
    "Osteoporosis Medications and Medication-Related Osteonecrosis of the Jaw": "骨粗鬆症治療薬と顎骨壊死（MRONJ）。ビスフォスフォネート系薬剤のリスク、歯科治療前の注意点、予防策。",
    "Sjögren Disease": "シェーグレン症候群と口腔の健康。ドライマウスの管理、むし歯予防、唾液腺ケアの方法。",
    "Sleep Apnea (Obstructive)": "閉塞性睡眠時無呼吸症候群と歯科。口腔内装置（マウスピース）による治療、歯科での早期発見のサイン。",
    "Tobacco Use and Cessation": "喫煙・タバコ使用と口腔の健康。歯周病・口腔がんのリスク、電子タバコの影響、禁煙支援と口腔健康の改善。",
    "Xerostomia (Dry Mouth)": "口腔乾燥症（ドライマウス）の原因と対策。薬剤性ドライマウス、唾液分泌促進法、むし歯予防、日常のケア方法。",
    "X-Rays/Radiographs": "歯科レントゲン撮影の安全性。被ばく量の実際、妊娠中の撮影、小児への配慮、デジタルX線の利点。",
    "Hypophosphatasia and X-Linked Hypophosphatemia": "低ホスファターゼ症と口腔症状。乳歯の早期脱落、歯のエナメル質異常、歯科での早期発見。",
    "Nutrition and Oral Health": "栄養と口腔の健康。食事がむし歯・歯周病に与える影響、口腔健康に良い食品、ビタミンD・カルシウムの役割。",
}


def load_csv():
    csv_path = project_root / "data" / "ada_topics.csv"
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def update_csv(ada_topic: str, article_id: str):
    csv_path = project_root / "data" / "ada_topics.csv"
    rows = load_csv()
    for row in rows:
        if row["ada_topic"] == ada_topic:
            row["article_id"] = article_id
            row["status"] = "作成済み"
            break
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def generate_one(ada_topic: str, prompt: str):
    """1つのトピックの記事を生成"""
    from app.services.article_service import ArticleService
    from app.services.topic_generator import TopicGenerator
    from app.state import revoke_approval

    print(f"\n{'='*60}")
    print(f"生成開始: {ada_topic}")
    print(f"{'='*60}")

    # トピック分析
    print("  トピック分析中...")
    gen = TopicGenerator()
    topic = gen.generate(prompt)
    print(f"  → ID: {topic['id']}, タイトル: {topic['title']}")

    # 記事生成
    print("  記事生成中...")
    service = ArticleService()
    try:
        result = service.generate_from_topic(
            topic=topic,
            category_name=topic.get("category_name", ""),
            age_range=topic.get("age_range", ""),
            progress_callback=lambda msg: print(f"    {msg}"),
        )
        service.save_result(result)
        print(f"  → 品質スコア: {result.quality_score}")

        # 未承認で登録
        revoke_approval(result.topic_id)

        # CSV更新
        update_csv(ada_topic, result.topic_id)
        print(f"  → 完了: {result.topic_id}")

        return result.topic_id
    except Exception as e:
        print(f"  → エラー: {e}")
        return None
    finally:
        service.close()


def main():
    rows = load_csv()
    pending = [r for r in rows if r["status"] == "未作成" and r["ada_topic"] in TOPIC_PROMPTS]

    print(f"未作成トピック: {len(pending)}件")

    for i, row in enumerate(pending, 1):
        ada_topic = row["ada_topic"]
        prompt = TOPIC_PROMPTS[ada_topic]
        print(f"\n[{i}/{len(pending)}] {ada_topic}")
        try:
            generate_one(ada_topic, prompt)
        except Exception as e:
            print(f"  スキップ（エラー）: {e}")
        # API負荷を避けるため少し待つ
        if i < len(pending):
            time.sleep(5)

    print(f"\n{'='*60}")
    print("全トピック処理完了")


if __name__ == "__main__":
    main()
