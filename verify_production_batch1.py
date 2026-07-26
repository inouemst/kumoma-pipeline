# -*- coding: utf-8 -*-
import json
import gates as g

fulltext_full = json.load(open("batch1_fulltext_full.json", encoding="utf-8"))
data = json.load(open("production_batch1.json", encoding="utf-8"))
index = json.load(open("index.json", encoding="utf-8"))
works = {w["作品ID"]: w for w in index["作品"]}

written = {k: v for k, v in data.items() if v.get("案内文")}
print(f"案内文あり: {len(written)}/{len(data)}")

gate_ok = 0
fails = []
for wid, v in written.items():
    gt = v["案内文"]
    r = g.run_all_gates(wid, gt, fulltext_full[wid])
    if r["総合判定"] == "OK":
        gate_ok += 1
    else:
        fails.append((wid, r))

print(f"総合ゲート通過率: {gate_ok}/{len(written)} = {gate_ok/len(written):.1%}")
for wid, r in fails:
    print(" NG:", wid, r["第三層_固有名詞照合"]["本文に不在"], r["第四層_現代語ゲート"]["混入語"],
          r["第五層_文字数"], r["第五層_評価語"]["評価語"], r["第五層_結末示唆"]["結末示唆語"])

# 著者名の言及チェック(本文に無いのに著者名を書いていないか)
print("\n--- 著者名言及チェック ---")
leak = 0
for wid, v in written.items():
    w = works.get(wid, {})
    author = (w.get("著者") or "").split()[0] if w.get("著者") else ""
    if author and len(author) >= 2 and author in v["案内文"] and author not in fulltext_full.get(wid, ""):
        print(" 著者名漏出の疑い:", wid, author, v["案内文"])
        leak += 1
print(f"著者名漏出の疑いのある件数: {leak}")

# ラベル語彙チェック
import label_vocab as lv
print("\n--- ラベル語彙チェック ---")
bad_labels = 0
for wid, v in written.items():
    labels = v.get("ラベル", {})
    for axis, vocab in lv.ALL_AXES.items():
        for val in labels.get(axis, []) or []:
            if val not in vocab:
                print(" 語彙外:", wid, axis, val)
                bad_labels += 1
print(f"語彙外のラベル件数: {bad_labels}")
