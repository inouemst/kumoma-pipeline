# -*- coding: utf-8 -*-
"""第2段階(露出率60%以上90%未満・物語系)143件の遡及修正用データを準備する。
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

    stage2_meta = {}
    stage2_input = {}
    stage2_full = {}
    stage2_old_guide = {}
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
            if not (is_narrative and 0.6 <= rate < 0.9):
                continue
            ft = full.get(wid, "")
            sliced, cut = new_input_slice(ft, chars)
            tier = "B" if chars < 1600 else "A"  # 想定上は全件A型のはず
            author_str = (idx_by_id.get(wid, {}) or {}).get("著者") or ""
            if not author_str.strip():
                empty_author.append(wid)
            stage2_meta[wid] = {
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
            stage2_input[wid] = sliced
            stage2_full[wid] = ft
            stage2_old_guide[wid] = v.get("案内文")

    json.dump(stage2_meta, open("stage2_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(stage2_input, open("stage2_input.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(stage2_full, open("stage2_fulltext_full.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(stage2_old_guide, open("stage2_old_guide.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    n_a = sum(1 for v in stage2_meta.values() if v["型"] == "A")
    n_b = sum(1 for v in stage2_meta.values() if v["型"] == "B")
    print(f"対象: {len(stage2_meta)}件 (A型{n_a}件 / B型{n_b}件)")
    print(f"著者名が空の作品: {len(empty_author)}件", empty_author if empty_author else "")
    print("出力: stage2_meta.json / stage2_input.json / stage2_fulltext_full.json / stage2_old_guide.json")


if __name__ == "__main__":
    main()
