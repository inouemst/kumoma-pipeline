# -*- coding: utf-8 -*-
"""
works_resolved.jsonl の各作品について、本文XHTMLファイルを探して解析し、
index.json / authors.json / errors.log を生成する。

冪等性：処理済み作品IDは state/checkpoint.jsonl に随時追記し、
再実行時はスキップする（--fresh で初期化）。
"""
import json
import glob
import os
import sys
import argparse
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))
import body_parser as bp

REPO = "/home/claude/aozorabunko"
WORKS_PATH = "/home/claude/phase1/state/works_resolved.jsonl"
CHECKPOINT_PATH = "/home/claude/phase1/state/checkpoint.jsonl"
ERRORS_PATH = "/home/claude/phase1/out/errors.log"
INDEX_OUT = "/home/claude/phase1/out/index.json"
AUTHORS_OUT = "/home/claude/phase1/out/authors.json"

JST = timezone(timedelta(hours=9))


def find_body_file(author_dir: str, work_id: str):
    # 命名規則は {作品ID}_{ファイルID}.html が基本だが、
    # {作品ID}.html （ファイルID無し）という別パターンも実在する（第4便で発見）。
    # 「本文ファイルが存在しない」343件のうち116件がこのパターンの見落としだった。
    pattern = f"{REPO}/cards/{author_dir}/files/{work_id}_*.html"
    matches = glob.glob(pattern)
    if not matches:
        no_suffix = f"{REPO}/cards/{author_dir}/files/{work_id}.html"
        if os.path.exists(no_suffix):
            matches = [no_suffix]
    if not matches:
        return None
    if len(matches) > 1:
        matches.sort()
    return matches[0]


def load_checkpoint():
    done = {}
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                done[rec["work_id"]] = rec
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="先頭N件のみ処理（試験実行用）")
    ap.add_argument("--fresh", action="store_true", help="チェックポイントを破棄して最初から")
    args = ap.parse_args()

    if args.fresh and os.path.exists(CHECKPOINT_PATH):
        os.remove(CHECKPOINT_PATH)

    works = []
    with open(WORKS_PATH, encoding="utf-8") as f:
        for line in f:
            works.append(json.loads(line))
    works.sort(key=lambda w: int(w["work_id"]))

    if args.limit:
        works = works[:args.limit]

    done = load_checkpoint()
    print(f"total works to consider: {len(works)}, already done: {len(done)}")

    checkpoint_f = open(CHECKPOINT_PATH, "a", encoding="utf-8")
    n_new_ok = 0
    n_new_err = 0

    for w in works:
        wid = w["work_id"]
        if wid in done:
            continue

        author_dir = w["card_path"].split("/")[1]
        body_path = find_body_file(author_dir, wid)

        if body_path is None:
            rec = {"work_id": wid, "status": "error", "reason": "body_file_not_found"}
            checkpoint_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            checkpoint_f.flush()
            n_new_err += 1
            continue

        try:
            measured = bp.process_body_file(body_path, w["mojizukai"])
        except bp.ParseError as e:
            rec = {"work_id": wid, "status": "error", "reason": f"parse_error: {e}", "body_path": body_path}
            checkpoint_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            checkpoint_f.flush()
            n_new_err += 1
            continue
        except Exception as e:
            rec = {"work_id": wid, "status": "error", "reason": f"unexpected: {type(e).__name__}: {e}", "body_path": body_path}
            checkpoint_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            checkpoint_f.flush()
            n_new_err += 1
            continue

        m = __import__("re").search(r"files/(\d+_\d+)\.html$", body_path)
        file_id = m.group(1) if m else os.path.basename(body_path).replace(".html", "")

        rec = {
            "work_id": wid,
            "status": "ok",
            "title": w["title"],
            "subtitle": w["subtitle"],
            "author_name": w["author_name"],
            "author_id": w["author_id"],
            "translator_name": w["translator_name"],
            "translator_id": w["translator_id"],
            "mojizukai": w["mojizukai"],
            "card_path": w["card_path"],
            "body_url_id": file_id,
            "measured": measured,
        }
        checkpoint_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        checkpoint_f.flush()
        n_new_ok += 1

    checkpoint_f.close()
    print(f"newly processed: ok={n_new_ok}, error={n_new_err}")


if __name__ == "__main__":
    main()
