# -*- coding: utf-8 -*-
"""batch3_draft_group0〜6.json(全97件)をproduction_batch3.json形式にまとめる。"""
import json

files = [f"batch3_draft_group{i}.json" for i in range(7)]

ids_all = json.load(open("next_batch_ids.json", encoding="utf-8"))
print("対象97件:", len(ids_all))

merged = {}
for fn in files:
    data = json.load(open(fn, encoding="utf-8"))
    for wid, v in data.items():
        merged[wid] = {
            "案内文": v["案内文"],
            "案内文なし理由": None,
            "固有名詞": v["固有名詞"],
            "ラベル": v["ラベル"],
        }

print("マージ件数:", len(merged))

missing = [wid for wid in ids_all if wid not in merged]
print("未生成:", missing)

out = {wid: merged[wid] for wid in ids_all if wid in merged}
json.dump(out, open("production_batch3.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("production_batch3.json 保存完了。件数:", len(out))
