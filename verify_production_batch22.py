# -*- coding: utf-8 -*-
import json
import gates as g
import label_vocab as lv
import statistics

fulltext_full = json.load(open("batch22_fulltext_full.json", encoding="utf-8"))
data = json.load(open("production_batch22.json", encoding="utf-8"))
index = json.load(open("index.json", encoding="utf-8"))
works = {w["作品ID"]: w for w in index["作品"]}

written = {k: v for k, v in data.items() if v.get("案内文")}
print(f"案内文あり: {len(written)}/{len(data)}")

lens = [len(v["案内文"]) for v in written.values()]
print(f"平均字数: {statistics.mean(lens):.1f} (最小{min(lens)} 最大{max(lens)})")

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

print("\n--- 著者名言及チェック ---")
# STAGE2_SPEC.md 1-2節の方式: index.jsonの著者欄を「、」で分割し、
# 共著・雅号を含む全ての氏名候補(姓名連結+姓・名それぞれ)を照合する。
# 旧方式(.split()[0]で先頭トークンのみ)は共著の2人目・雅号を見逃していたため廃止。
import re
leak = 0
for wid, v in written.items():
    w = works.get(wid, {})
    au_string = w.get("著者") or ""
    text = v["案内文"]
    names = set()
    for part in re.split(r"[、,]", au_string):
        part = part.replace("→", "").strip()
        if not part:
            continue
        names.add(part.replace(" ", "").replace("　", ""))
        for tok in re.split(r"[ 　]+", part):
            if len(tok) >= 2:
                names.add(tok)
    for nm in names:
        if nm and nm in text and nm not in fulltext_full.get(wid, ""):
            print(" 著者名漏出の疑い:", wid, nm, "(著者欄:", au_string, ")", text)
            leak += 1
            break
print(f"著者名漏出の疑いのある件数: {leak}")

print("\n--- ラベル語彙チェック(軸ごとの正しさも含む) ---")
bad_labels = 0
for wid, v in written.items():
    labels = v.get("ラベル", {})
    for axis, vocab in lv.ALL_AXES.items():
        for val in labels.get(axis, []) or []:
            if val not in vocab:
                print(" 語彙外:", wid, axis, val)
                bad_labels += 1
print(f"語彙外のラベル件数: {bad_labels}")

print("\n--- 文末多様性チェック ---")
r_ending = g.check_ending_diversity_v2({wid: v["案内文"] for wid, v in written.items()})
print(json.dumps(r_ending, ensure_ascii=False, indent=1))

print("\n--- 97件到達確認 ---")
next_ids = json.load(open("next_batch_ids.json", encoding="utf-8"))
missing = [i for i in next_ids if i not in data]
print("next_batch_idsのうちproduction_batch22.jsonに存在しないもの:", missing)
