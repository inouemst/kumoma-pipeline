# -*- coding: utf-8 -*-
"""案内文の下書きを、全文JSONをエージェントに読ませずに検証するためのCLIツール。
全文データ(数百万字)はこのスクリプトの中だけで使い、結果(合否・不在語リスト)だけを
標準出力に返す。エージェントはこのスクリプトの出力だけを見ればよく、
batchN_fulltext_full.json を Read/Get-Content で直接開く必要はない。

使い方:
  python gate_check_batch.py <N> <作品ID> "<案内文>"
      → その1件だけを全文照合して結果を表示(下書き段階でこまめに使う)

  python gate_check_batch.py <N> --all production_batchN.json
      → production_batchN.json全体をまとめて検証し、不合格の作品IDと理由だけを一覧表示
"""
import json
import sys
import gates as g


def check_one(n, wid, guide_text):
    fulltext_full = json.load(open(f"batch{n}_fulltext_full.json", encoding="utf-8"))
    if wid not in fulltext_full:
        print(f"NG: 作品ID {wid} が batch{n}_fulltext_full.json に存在しません")
        return
    r = g.run_all_gates(wid, guide_text, fulltext_full[wid])
    print(f"作品ID {wid}: {r['総合判定']}")
    if r["総合判定"] != "OK":
        if r["第三層_固有名詞照合"]["本文に不在"]:
            print("  本文に不在の固有名詞:", r["第三層_固有名詞照合"]["本文に不在"])
        if r["第四層_現代語ゲート"]["混入語"]:
            print("  現代語ゲート抵触:", r["第四層_現代語ゲート"]["混入語"])
        if r["第五層_文字数"]["判定"] != "OK":
            print("  字数:", r["第五層_文字数"]["文字数"], "字(規格60-100字)")
        if r["第五層_評価語"]["評価語"]:
            print("  評価語:", r["第五層_評価語"]["評価語"])
        if r["第五層_結末示唆"]["結末示唆語"]:
            print("  結末示唆語:", r["第五層_結末示唆"]["結末示唆語"])


def check_all(n, prod_file):
    fulltext_full = json.load(open(f"batch{n}_fulltext_full.json", encoding="utf-8"))
    data = json.load(open(prod_file, encoding="utf-8"))
    written = {k: v for k, v in data.items() if v.get("案内文")}
    ok = 0
    fails = []
    for wid, v in written.items():
        r = g.run_all_gates(wid, v["案内文"], fulltext_full.get(wid, ""))
        if r["総合判定"] == "OK":
            ok += 1
        else:
            reasons = []
            if r["第三層_固有名詞照合"]["本文に不在"]:
                reasons.append("不在語:" + ",".join(r["第三層_固有名詞照合"]["本文に不在"]))
            if r["第四層_現代語ゲート"]["混入語"]:
                reasons.append("現代語:" + ",".join(r["第四層_現代語ゲート"]["混入語"]))
            if r["第五層_文字数"]["判定"] != "OK":
                reasons.append(f"字数:{r['第五層_文字数']['文字数']}")
            if r["第五層_評価語"]["評価語"]:
                reasons.append("評価語:" + ",".join(r["第五層_評価語"]["評価語"]))
            if r["第五層_結末示唆"]["結末示唆語"]:
                reasons.append("結末示唆:" + ",".join(r["第五層_結末示唆"]["結末示唆語"]))
            fails.append((wid, "; ".join(reasons)))

    print(f"案内文あり: {len(written)}/{len(data)}")
    print(f"総合ゲート通過率: {ok}/{len(written)} = {ok/len(written):.1%}" if written else "0件")
    if fails:
        print(f"\n不合格 {len(fails)}件:")
        for wid, reason in fails:
            print(f"  {wid}: {reason}")

    ending = g.check_ending_diversity_v2({wid: v["案内文"] for wid, v in written.items()})
    print("\n文末多様性:", ending["判定"])
    if ending["形式名詞軸_閾値超過"] or ending["用言軸_閾値超過"]:
        print("  超過:", ending["形式名詞軸_閾値超過"], ending["用言軸_閾値超過"])


if __name__ == "__main__":
    n = sys.argv[1]
    if sys.argv[2] == "--all":
        check_all(n, sys.argv[3])
    else:
        wid = sys.argv[2]
        guide_text = sys.argv[3]
        check_one(n, wid, guide_text)
