# -*- coding: utf-8 -*-
"""第3段階(露出率40%以上60%未満・物語系)152件の遡及修正用データを準備する。
GUIDE_TEXT_SPEC_V2.md 2章の新ルールで入力を再計算し、
エージェントに渡す素材(新入力・全文・メタ・旧案内文)を出力する。

STAGE2_SPEC.md 1章の決定により、著者名は batchN_meta.json の著者ID→authors.json
という経路(共著・著者ID空で欠落するケースがあった)をやめ、index.jsonの著者欄を
直接使う。
"""
import json
import glob
import re

NARRATIVE_FORMS = {"小説", "童話", "戯曲", "脚本"}


def load_index_authors():
    index = json.load(open("index.json", encoding="utf-8"))
    idx_by_id = {w["作品ID"]: w for w in index["作品"]}
    return idx_by_id


def new_input_slice(full_text, chars):
    cut = min(4000, max(300, int(chars * 0.25)))
    return full_text[:cut], cut


def main():
    idx_by_id = load_index_authors()
    batch_nums = sorted(
        int(re.search(r"batch(\d+)_meta\.json", f).group(1))
        for f in glob.glob("batch*_meta.json")
    )

    stage3_meta = {}
    stage3_input = {}
    stage3_full = {}
    stage3_old_guide = {}
    empty_author = []

    for n in batch_nums:
        meta = json.load(open(f"batch{n}_meta.json", encoding="utf-8"))
        prod = json.load(open(f"production_batch{n}.json", encoding="utf-8"))
        full = json.load(open(f"batch{n}_fulltext_full.json", encoding="utf-8"))
        for wid, v in prod.items():
            m = meta.get(wid, {})
            chars = m.get("文字数", 0)
            if not chars:
                continue
            rate = min(4000, chars) / chars
            labels = v.get("ラベル", {}) or {}
            forms = labels.get("形式") or []
            is_narrative = bool(set(forms) & NARRATIVE_FORMS)
            if not (is_narrative and 0.4 <= rate < 0.6):
                continue
            ft = full.get(wid, "")
            sliced, cut = new_input_slice(ft, chars)
            tier = "B" if chars < 1600 else "A"  # 想定上は全件A型のはず
            author_str = (idx_by_id.get(wid, {}) or {}).get("著者") or ""
            if not author_str.strip():
                empty_author.append(wid)
            stage3_meta[wid] = {
                "作品ID": wid,
                "作品名": m.get("作品名", ""),
                "著者名": author_str,
                "文字遣い": m.get("文字遣い", ""),
                "文字数": chars,
                "新入力字数": cut,
                "元バッチ": n,
                "型": tier,
                "旧ラベル": labels,
            }
            stage3_input[wid] = sliced
            stage3_full[wid] = ft
            stage3_old_guide[wid] = v.get("案内文")

    json.dump(stage3_meta, open("stage3_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(stage3_input, open("stage3_input.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(stage3_full, open("stage3_fulltext_full.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(stage3_old_guide, open("stage3_old_guide.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    n_a = sum(1 for v in stage3_meta.values() if v["型"] == "A")
    n_b = sum(1 for v in stage3_meta.values() if v["型"] == "B")
    print(f"対象: {len(stage3_meta)}件 (A型{n_a}件 / B型{n_b}件)")
    print(f"著者名が空の作品: {len(empty_author)}件", empty_author if empty_author else "")
    print("出力: stage3_meta.json / stage3_input.json / stage3_fulltext_full.json / stage3_old_guide.json")


if __name__ == "__main__":
    main()
