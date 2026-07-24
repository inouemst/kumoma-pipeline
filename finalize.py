# -*- coding: utf-8 -*-
import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict

CHECKPOINT_PATH = "/home/claude/phase1/state/checkpoint.jsonl"
INDEX_OUT = "/home/claude/phase1/out/index.json"
AUTHORS_OUT = "/home/claude/phase1/out/authors.json"
ERRORS_OUT = "/home/claude/phase1/out/errors.log"

JST = timezone(timedelta(hours=9))
CARD_BASE = "https://www.aozora.gr.jp/"


def reading_bucket_from_minutes(m):
    if m <= 5:
        return "5分以内"
    if m <= 15:
        return "15分以内"
    if m <= 30:
        return "30分以内"
    if m <= 60:
        return "1時間以内"
    return "それ以上"


def main():
    works = []
    errors = []

    with open(CHECKPOINT_PATH, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec["status"] == "error":
                errors.append(rec)
                continue

            m = rec["measured"]
            author_dir = rec["card_path"].split("/")[1]
            card_url = CARD_BASE + rec["card_path"]
            body_url_id_val = rec["body_url_id"]
            work_id = rec["work_id"]
            body_url = f"{CARD_BASE}cards/{author_dir}/files/{body_url_id_val}.html"

            entry = {
                "作品ID": work_id,
                "作品名": rec["title"] + (("　" + rec["subtitle"]) if rec["subtitle"] else ""),
                "著者": rec["author_name"],
                "著者ID": rec["author_id"],
                "訳者": rec["translator_name"],
                "訳者ID": rec["translator_id"],
                "文字遣い": rec["mojizukai"],
                "図書カードURL": card_url,
                "本文URL": body_url,
                "計測値": {
                    "文字数": m["n_chars"],
                    "想定読解速度_字毎分": m["reading_speed_cpm"],
                    "速度の根拠": m["reading_speed_reason"],
                    "推定読了時間_分": m["reading_minutes"],
                    "読了時間区分": m["reading_bucket"],
                    "漢字含有率": m["kanji_ratio"],
                    "会話文比率": m["dialogue_ratio"],
                    "ルビ密度": m["ruby_density"],
                    "旧仮名": m["is_kyu_kana"],
                    "文語体": m["is_bungo"],
                },
                "はじまりの一文": m["opening_sentence"],
                "はじまりの一文_省略": m.get("opening_truncated", False),
                "はじまりの一文_要確認": m.get("opening_needs_review", False),
                "クレジット": {
                    "底本": m["credits"]["底本"],
                    "入力者": m["credits"]["入力者"],
                    "校正者": m["credits"]["校正者"],
                    "初出": m["credits"]["初出"],
                },
            }
            if m["credits"].get("翻訳者クレジット"):
                entry["クレジット"]["翻訳者クレジット"] = m["credits"]["翻訳者クレジット"]
            if m.get("n_bad_chars", 0) > 0:
                entry["文字化け数"] = m["n_bad_chars"]

            works.append(entry)

    works.sort(key=lambda w: int(w["作品ID"]))

    # 対象外処理（第4便）：本文が実質存在しない2件を index.json から除外する。
    # 343件（body_file_not_found）は元々 status=error のため works には含まれていない。
    # こちらは status=ok だが文字数0（表題のみ／絵本で画像のみ）の2件を明示的に除く。
    NO_TEXT_EXCLUDE = {
        "48490": "本文なし（表題のみ、原民喜「渚」）",
        "54925": "本文が画像のみ（絵本、ケイト・グリーナウェイ「マリゴールド・ガーデン」）",
    }
    excluded_no_text = [w for w in works if w["作品ID"] in NO_TEXT_EXCLUDE]
    works = [w for w in works if w["作品ID"] not in NO_TEXT_EXCLUDE]

    n_body_not_found = sum(1 for e in errors if e["reason"] == "body_file_not_found")
    taishogai = {
        "件数": n_body_not_found + len(excluded_no_text),
        "内訳": {
            "本文ファイルが取得できない（著作権存続・外部リンク等）": n_body_not_found,
            "本文が実質存在しない（表題のみ／画像のみ）": len(excluded_no_text),
        },
    }

    index_obj = {
        "生成日時": datetime.now(JST).isoformat(),
        "作品数": len(works),
        "対象外件数": taishogai,
        "作品": works,
    }

    with open(INDEX_OUT, "w", encoding="utf-8") as f:
        json.dump(index_obj, f, ensure_ascii=False, indent=1)

    # authors.json: 著者ごとの集約
    by_author = defaultdict(lambda: {"作品数": 0, "文字遣い分布": defaultdict(int), "総文字数": 0, "作品ID一覧": []})
    for w in works:
        aid = w["著者ID"]
        aname = w["著者"]
        if aid is None:
            continue
        # 複数著者（"、"区切り）は最初の著者にのみ集計する（簡略化）
        first_id = aid.split("、")[0]
        first_name = aname.split("、")[0] if aname else None
        rec = by_author[first_id]
        rec["著者名"] = first_name
        rec["作品数"] += 1
        rec["文字遣い分布"][w["文字遣い"]] += 1
        rec["総文字数"] += w["計測値"]["文字数"]
        rec["作品ID一覧"].append(w["作品ID"])

    authors_list = []
    for aid, rec in by_author.items():
        moji_dist = dict(rec["文字遣い分布"])
        dominant = max(moji_dist.items(), key=lambda kv: kv[1])[0] if moji_dist else None
        authors_list.append({
            "著者ID": aid,
            "著者名": rec["著者名"],
            "作品数": rec["作品数"],
            "総文字数": rec["総文字数"],
            "代表的な文字遣い": dominant,
            "文字遣い分布": moji_dist,
        })
    authors_list.sort(key=lambda a: -a["作品数"])

    authors_obj = {
        "生成日時": datetime.now(JST).isoformat(),
        "著者数": len(authors_list),
        "著者": authors_list,
    }
    with open(AUTHORS_OUT, "w", encoding="utf-8") as f:
        json.dump(authors_obj, f, ensure_ascii=False, indent=1)

    # errors.log
    with open(ERRORS_OUT, "w", encoding="utf-8") as f:
        f.write(f"# 第一段階 処理エラー・対象外一覧\n")
        f.write(f"# 生成日時: {datetime.now(JST).isoformat()}\n")
        f.write(f"# 総エラー件数: {len(errors)}\n")
        f.write(f"# うち本文ファイル取得不可（著作権存続・外部リンク等、検証済み）: {n_body_not_found}\n")
        f.write(f"# 別途、本文が実質存在しないため index.json から除外: {len(excluded_no_text)}\n\n")
        for e in errors:
            f.write(f"作品ID={e['work_id']}\t理由={e['reason']}\tpath={e.get('body_path', '-')}\n")
        f.write("\n# --- 本文が実質存在しないための除外（status=ok だが対象外） ---\n")
        for w in excluded_no_text:
            reason = NO_TEXT_EXCLUDE[w["作品ID"]]
            f.write(f"作品ID={w['作品ID']}\t理由={reason}\tpath=-\n")

    print(f"works: {len(works)}")
    print(f"authors: {len(authors_list)}")
    print(f"errors: {len(errors)}")

    import os
    sz = os.path.getsize(INDEX_OUT)
    print(f"index.json size: {sz:,} bytes ({sz/1024/1024:.2f} MB)")


if __name__ == "__main__":
    main()
