# -*- coding: utf-8 -*-
"""第1段階169件の修正案(stage1_corrections.json)を、
kumoma_prototype.htmlのD配列とstate/checkpoint.jsonlに反映する。
GUIDE_TEXT_SPEC_V2.md 6-2節の決定(新しい行を追記・後勝ち・由来=revision_stage1)に従う。
"""
import json
import re

corr = json.load(open("stage1_corrections.json", encoding="utf-8"))
meta = json.load(open("stage1_meta.json", encoding="utf-8"))

PATH = "kumoma_prototype.html"
text = open(PATH, encoding="utf-8").read()
m = re.search(r"const D=(\[.*\]);", text)
D = json.loads(m.group(1))
by_id = {w[0]: w for w in D}

n_updated = 0
n_missing = 0
for wid, v in corr.items():
    w = by_id.get(wid)
    if w is None:
        print("警告: index.jsonに無いID", wid)
        n_missing += 1
        continue
    w[16] = v["案内文"]
    n_updated += 1

print("D配列更新件数:", n_updated, "見つからず:", n_missing)

new_d_literal = "const D=" + json.dumps(D, ensure_ascii=False, separators=(",", ":")) + ";"
text = text[: m.start()] + new_d_literal + text[m.end():]
open(PATH, "w", encoding="utf-8").write(text)

with open("state/checkpoint.jsonl", "a", encoding="utf-8") as f:
    for wid, v in corr.items():
        m_info = meta.get(wid, {})
        rec = {
            "作品ID": wid,
            "案内文": v["案内文"],
            "案内文なし理由": None,
            "ラベル": m_info.get("旧ラベル", {}),
            "由来": "revision_stage1",
        }
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
print("checkpoint.jsonlに169件追記完了")
