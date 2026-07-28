# -*- coding: utf-8 -*-
"""production_batch4.json の独立検証。batch1/2/3 と同じ手法。gates.py を直接実行する。"""
import json
import gates as g
import label_vocab as lv

fulltext_full = json.load(open("batch4_fulltext_full.json", encoding="utf-8"))
data = json.load(open("production_batch4.json", encoding="utf-8"))
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

# 著者名の言及チェック
print("\n--- 著者名言及チェック ---")
leak = 0
for wid, v in written.items():
    w = works.get(wid, {})
    author = (w.get("著者") or "").split()[0] if w.get("著者") else ""
    if author and len(author) >= 2 and author in v["案内文"] and author not in fulltext_full.get(wid, ""):
        print(" 著者名漏出の疑い:", wid, author, v["案内文"])
        leak += 1
print(f"著者名漏出の疑いのある件数: {leak}")

# 作品名の言及チェック(参考。固有名詞として正当な場合は許容/8章 羅生門の例に準拠)
print("\n--- 作品名言及チェック(参考) ---")
title_leak = 0
for wid, v in written.items():
    w = works.get(wid, {})
    title = w.get("作品名") or ""
    if title and len(title) >= 2 and title in v["案内文"]:
        print(" 参考:", wid, title, v["案内文"])
        title_leak += 1
print(f"作品名と同一文字列を含む件数(参考、固有名詞なら許容): {title_leak}")

# ラベル語彙チェック
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

# 文末多様性チェック
print("\n--- 文末多様性チェック ---")
r_ending = g.check_ending_diversity_v2({wid: v["案内文"] for wid, v in written.items()})
print(json.dumps(r_ending, ensure_ascii=False, indent=1))

# 97件到達確認
print("\n--- 97件到達確認 ---")
ids_all = json.load(open("next_batch_ids.json", encoding="utf-8"))
missing = [wid for wid in ids_all if wid not in data]
print("次バッチIDのうちproduction_batch4.jsonに存在しないもの:", missing)
no_guide = [wid for wid in ids_all if not data.get(wid, {}).get("案内文")]
print("案内文なし(理由記録が必要な件数):", len(no_guide), no_guide)
