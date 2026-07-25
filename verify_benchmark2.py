# -*- coding: utf-8 -*-
import json
import gates as g

fulltext_full = json.load(open("fulltext_100_full.json", encoding="utf-8"))
drafts = json.load(open("drafts_batch1.json", encoding="utf-8"))
labels1 = json.load(open("labels_pass1.json", encoding="utf-8"))

MONOGATARI = {"小説", "童話", "戯曲", "詩", "書簡"}
ZUIHITSU = {"随筆", "評論"}


def bucket(forms):
    if forms is None:
        return None
    if isinstance(forms, str):
        forms = [forms]
    forms = set(forms)
    if forms & MONOGATARI:
        return "monogatari"
    if forms & ZUIHITSU:
        return "zuihitsu"
    return None


def get_form(entry):
    if "形式" in entry:
        return entry["形式"]
    return entry.get("ラベル", {}).get("形式")


for n in [3, 8, 15]:
    fn = f"benchmark2_n{n}.json"
    data = json.load(open(fn, encoding="utf-8"))
    written = {k: v for k, v in data.items() if v.get("案内文")}

    n_written = len(written)
    gate3_ok = 0
    gate4_ok = 0
    len_ok = 0
    rank_ok = 0
    end_ok = 0
    jaccards = []
    type_match = 0
    type_total = 0
    gtexts = {}

    for wid, v in written.items():
        gt = v["案内文"]
        gtexts[wid] = gt
        r = g.run_all_gates(wid, gt, fulltext_full[wid])
        if r["第三層_固有名詞照合"]["判定"] == "OK":
            gate3_ok += 1
        if r["第四層_現代語ゲート"]["判定"] == "OK":
            gate4_ok += 1
        if r["第五層_文字数"]["判定"] == "OK":
            len_ok += 1
        if r["第五層_評価語"]["判定"] == "OK":
            rank_ok += 1
        if r["第五層_結末示唆"]["判定"] == "OK":
            end_ok += 1

        if wid in drafts and drafts[wid].get("固有名詞"):
            draft_nouns = set(drafts[wid]["固有名詞"])
            my_nouns = set(r["第三層_固有名詞照合"]["候補"])
            union = draft_nouns | my_nouns
            if union:
                jaccards.append(len(draft_nouns & my_nouns) / len(union))

        if wid in labels1:
            ref_bucket = bucket(get_form(labels1[wid]))
            my_bucket = bucket(get_form(v))
            if ref_bucket and my_bucket:
                type_total += 1
                if ref_bucket == my_bucket:
                    type_match += 1

    ending = g.check_ending_diversity_v2(gtexts)

    print(f"=== N={n} ===")
    print(f"  案内文あり: {n_written}/100")
    print(f"  第三層(固有名詞)通過率: {gate3_ok}/{n_written} = {gate3_ok/n_written:.1%}")
    print(f"  第四層(現代語)通過率: {gate4_ok}/{n_written} = {gate4_ok/n_written:.1%}")
    print(f"  字数規格達成率: {len_ok}/{n_written} = {len_ok/n_written:.1%}")
    print(f"  評価語なし: {rank_ok}/{n_written} = {rank_ok/n_written:.1%}")
    print(f"  結末示唆なし: {end_ok}/{n_written} = {end_ok/n_written:.1%}")
    if jaccards:
        print(f"  固有名詞Jaccard平均: {sum(jaccards)/len(jaccards):.3f} (n={len(jaccards)})")
    else:
        print("  固有名詞Jaccard平均: 参照データなし")
    if type_total:
        print(f"  型一致率: {type_match}/{type_total} = {type_match/type_total:.1%}")
    else:
        print("  型一致率: 参照データなし")
    print(f"  文末多様性: {ending['判定']}")
    print(f"    形式名詞軸超過: {ending['形式名詞軸_閾値超過']}")
    print(f"    用言軸超過: {ending['用言軸_閾値超過']}")

    overall = sum(
        1
        for wid, v in written.items()
        if g.run_all_gates(wid, v["案内文"], fulltext_full[wid])["総合判定"] == "OK"
    )
    print(f"  総合ゲート通過率: {overall}/{n_written} = {overall/n_written:.1%}")
    print()
