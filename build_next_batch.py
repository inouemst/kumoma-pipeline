# -*- coding: utf-8 -*-
"""checkpoint.jsonlから既完了IDを読み、優先順位リスト(ランキング)から次のバッチを選定する。
複数のranking_*.jsonファイルを順につなげて使う(151位以降を後から追加していく想定)。"""
import json
import glob

index = json.load(open("index.json", encoding="utf-8"))
works = {w["作品ID"]: w for w in index["作品"]}
under200 = set(json.load(open("under200_ids.json", encoding="utf-8-sig")))

done_ids = set()
with open("state/checkpoint.jsonl", encoding="utf-8") as f:
    for line in f:
        rec = json.loads(line)
        done_ids.add(rec["作品ID"])
print("既完了:", len(done_ids), "件")

ranking = []
for fn in sorted(glob.glob("ranking_*.json")):
    ranking.extend(json.load(open(fn, encoding="utf-8")))
print("ランキング読み込み合計:", len(ranking), "件（重複ファイルを跨ぐ可能性あり、下でIDにより重複排除）")

seen = set()
next_batch = []
for rank, title, author, wid in ranking:
    if wid in seen:
        continue
    seen.add(wid)
    if wid in done_ids or wid in under200:
        continue
    if wid not in works:
        continue
    next_batch.append(wid)
    if len(next_batch) >= 97:
        break

n_from_ranking = len(next_batch)
print("ランキングから確保:", n_from_ranking, "件")

# ランキング上位(複数年)がほぼ使い尽くされた場合のフォールバック:
# 作品ID昇順で埋める(人気順ではなくなるが、「育つ庭」モデルでは
# いずれ全件処理するため、順序の重要性は低下している)。
if len(next_batch) < 97:
    remaining_pool = sorted(
        (wid for wid in works if wid not in done_ids and wid not in under200 and wid not in seen),
        key=lambda x: int(x),
    )
    for wid in remaining_pool:
        next_batch.append(wid)
        if len(next_batch) >= 97:
            break
    print(f"ランキング切れのためID昇順で補充: {len(next_batch) - n_from_ranking}件追加")

print("次バッチ:", len(next_batch), "件")
json.dump(next_batch, open("next_batch_ids.json", "w", encoding="utf-8"), ensure_ascii=False)
print("next_batch_ids.json に保存(上書き)")
