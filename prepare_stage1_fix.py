# -*- coding: utf-8 -*-
"""第1段階(露出率90%以上・物語系)169件の遡及修正用データを準備する。
GUIDE_TEXT_SPEC_V2.md 2章の新ルールで入力を再計算し、
エージェントに渡す素材(新入力・ヒント・全文・メタ・旧案内文)を出力する。
"""
import json
import glob
import re

NARRATIVE_FORMS = {"小説", "童話", "戯曲", "脚本"}


def load_authors():
    d = json.load(open("authors.json", encoding="utf-8"))
    au_list = d.get("著者") or []
    return {a.get("著者ID"): a.get("著者名") for a in au_list}


def new_input_slice(full_text, chars):
    cut = min(4000, max(300, int(chars * 0.25)))
    return full_text[:cut], cut


def main():
    authors = load_authors()
    batch_nums = sorted(
        int(re.search(r"batch(\d+)_meta\.json", f).group(1))
        for f in glob.glob("batch*_meta.json")
    )

    stage1_meta = {}
    stage1_input = {}
    stage1_full = {}
    stage1_old_guide = {}

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
            if not (is_narrative and rate >= 0.9):
                continue
            ft = full.get(wid, "")
            sliced, cut = new_input_slice(ft, chars)
            tier = "B" if chars < 1600 else "A"
            stage1_meta[wid] = {
                "作品ID": wid,
                "作品名": m.get("作品名", ""),
                "著者ID": m.get("著者ID", ""),
                "著者名": authors.get(m.get("著者ID"), ""),
                "文字遣い": m.get("文字遣い", ""),
                "文字数": chars,
                "新入力字数": cut,
                "元バッチ": n,
                "型": tier,
                "旧ラベル": labels,
            }
            stage1_input[wid] = sliced
            stage1_full[wid] = ft
            stage1_old_guide[wid] = v.get("案内文")

    json.dump(stage1_meta, open("stage1_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(stage1_input, open("stage1_input.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(stage1_full, open("stage1_fulltext_full.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(stage1_old_guide, open("stage1_old_guide.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    n_a = sum(1 for v in stage1_meta.values() if v["型"] == "A")
    n_b = sum(1 for v in stage1_meta.values() if v["型"] == "B")
    print(f"対象: {len(stage1_meta)}件 (A型{n_a}件 / B型{n_b}件)")
    print("出力: stage1_meta.json / stage1_input.json / stage1_fulltext_full.json / stage1_old_guide.json")


if __name__ == "__main__":
    main()
