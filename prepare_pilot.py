# -*- coding: utf-8 -*-
"""PIPELINE_V2_SPEC.md 5章のパイロット(24件)用データを準備する。
pilot_ids.json で選定済みのIDについて、新ルール(25%切り出し)で入力を
再計算し、旧案内文との比較材料一式を出力する。
著者名はindex.jsonの著者欄から取得する(STAGE2_SPEC.md 1章の方式)。
"""
import json
import glob
import re

def load_index_authors():
    index = json.load(open("index.json", encoding="utf-8"))
    return {w["作品ID"]: w for w in index["作品"]}

def new_input_slice(full_text, chars):
    cut = min(4000, max(300, int(chars * 0.25)))
    return full_text[:cut], cut

def main():
    target_ids = set(json.load(open("pilot_ids.json", encoding="utf-8")))
    idx_by_id = load_index_authors()
    batch_nums = sorted(
        int(re.search(r"batch(\d+)_meta\.json", f).group(1))
        for f in glob.glob("batch*_meta.json")
    )

    pilot_meta = {}
    pilot_input = {}
    pilot_full = {}
    pilot_old_guide = {}

    for n in batch_nums:
        meta = json.load(open(f"batch{n}_meta.json", encoding="utf-8"))
        prod = json.load(open(f"production_batch{n}.json", encoding="utf-8"))
        full = None
        for wid in list(target_ids):
            if wid not in meta:
                continue
            if full is None:
                full = json.load(open(f"batch{n}_fulltext_full.json", encoding="utf-8"))
            m = meta[wid]
            v = prod.get(wid, {})
            chars = m.get("文字数", 0)
            ft = full.get(wid, "")
            sliced, cut = new_input_slice(ft, chars)
            labels = v.get("ラベル", {}) or {}
            forms = labels.get("形式") or []
            tier = "B" if chars < 1600 else "A"
            author_str = (idx_by_id.get(wid, {}) or {}).get("著者") or ""
            pilot_meta[wid] = {
                "作品ID": wid,
                "作品名": m.get("作品名", ""),
                "著者名": author_str,
                "文字遣い": m.get("文字遣い", ""),
                "文字数": chars,
                "新入力字数": cut,
                "元バッチ": n,
                "型": tier,
                "形式": forms,
                "旧ラベル": labels,
            }
            pilot_input[wid] = sliced
            pilot_full[wid] = ft
            pilot_old_guide[wid] = v.get("案内文")
            target_ids.discard(wid)

    if target_ids:
        print("警告: 見つからなかったID", target_ids)

    json.dump(pilot_meta, open("pilot_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(pilot_input, open("pilot_input.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(pilot_full, open("pilot_fulltext_full.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(pilot_old_guide, open("pilot_old_guide.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"対象: {len(pilot_meta)}件")
    print("出力: pilot_meta.json / pilot_input.json / pilot_fulltext_full.json / pilot_old_guide.json")

if __name__ == "__main__":
    main()
