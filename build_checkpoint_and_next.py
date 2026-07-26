# -*- coding: utf-8 -*-
"""state/checkpoint.jsonlを初期化し(N=15ベンチマーク分を既完了として記録)、
アクセスランキング順に次のバッチ(97件)を選定する。"""
import json
import os

os.makedirs("state", exist_ok=True)

index = json.load(open("index.json", encoding="utf-8"))
works = {w["作品ID"]: w for w in index["作品"]}
under200 = set(json.load(open("under200_ids.json", encoding="utf-8-sig")))
bench = json.load(open("benchmark2_n15.json", encoding="utf-8"))
ranking = json.load(open("ranking_top150.json", encoding="utf-8"))  # [rank,title,author,id]

# --- 1. checkpoint.jsonl: 既完了(97件)を記録 ---
done_ids = set()
with open("state/checkpoint.jsonl", "w", encoding="utf-8") as f:
    for wid, v in bench.items():
        if not v.get("案内文"):
            continue
        rec = {
            "作品ID": wid,
            "案内文": v["案内文"],
            "案内文なし理由": None,
            "ラベル": v.get("ラベル", {}),
            "由来": "benchmark2_n15(較正後ベンチマーク・本番採用)",
        }
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        done_ids.add(wid)
print("checkpoint.jsonl 初期化:", len(done_ids), "件")

# --- 2. 次のバッチ(97件)をランキング順に選定 ---
next_batch = []
for rank, title, author, wid in ranking:
    if wid in done_ids or wid in under200:
        continue
    if wid not in works:
        continue  # ランキングのIDがindex.jsonに無い(対象外作品等)
    next_batch.append(wid)
    if len(next_batch) >= 97:
        break

print("ランキング上位150件のうち、未処理で対象になったもの:", len(next_batch), "件")

json.dump(next_batch, open("next_batch_ids.json", "w", encoding="utf-8"), ensure_ascii=False)
print("next_batch_ids.json に保存")
