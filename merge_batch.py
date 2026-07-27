# -*- coding: utf-8 -*-
"""production_batchN.json を kumoma_prototype.html の D と checkpoint.jsonl に反映する汎用スクリプト。
使い方: python merge_batch.py 2  (production_batch2.json を取り込む)"""
import json
import re
import sys

n = sys.argv[1] if len(sys.argv) > 1 else "1"
batch_file = f"production_batch{n}.json"
PATH = "kumoma_prototype.html"

text = open(PATH, encoding="utf-8").read()
m = re.search(r"const D=(\[.*\]);", text)
D = json.loads(m.group(1))

batch = json.load(open(batch_file, encoding="utf-8"))

n_updated = 0
by_id = {w[0]: w for w in D}
for wid, v in batch.items():
    if not v.get("案内文"):
        continue
    w = by_id.get(wid)
    if w is None:
        print("警告: index.jsonに無いID", wid)
        continue
    w[16] = v["案内文"]
    labels = v.get("ラベル", {})
    form = (labels.get("形式") or [None])[0]
    mood = labels.get("読後感") or None
    w[17] = form
    w[18] = mood
    n_updated += 1

print("更新件数:", n_updated)

new_d_literal = "const D=" + json.dumps(D, ensure_ascii=False, separators=(",", ":")) + ";"
text = text[: m.start()] + new_d_literal + text[m.end():]
open(PATH, "w", encoding="utf-8").write(text)

with open("state/checkpoint.jsonl", "a", encoding="utf-8") as f:
    for wid, v in batch.items():
        rec = {
            "作品ID": wid,
            "案内文": v.get("案内文"),
            "案内文なし理由": v.get("案内文なし理由"),
            "ラベル": v.get("ラベル", {}),
            "由来": f"production_batch{n}",
        }
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
print("checkpoint.jsonlに追記完了")
