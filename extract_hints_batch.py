# -*- coding: utf-8 -*-
"""本文冒頭4,000字から、janomeで固有名詞候補を機械抽出し、
「本文に実在する正しい表記」のヒントリストを作る。
生成前にこれを見ておけば、旧字体・現代化ミスによる手戻りを減らせる。

使い方: python extract_hints_batch.py <N>
  batch{N}_fulltext_4000.json を読み、batch{N}_hints.json に保存する。
"""
import json
import sys
import gates as g

n = sys.argv[1]
fulltext_4000 = json.load(open(f"batch{n}_fulltext_4000.json", encoding="utf-8"))

hints = {}
for wid, text in fulltext_4000.items():
    candidates = g.extract_proper_noun_candidates_janome(text)
    hints[wid] = candidates

json.dump(hints, open(f"batch{n}_hints.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"batch{n}_hints.json に保存: {len(hints)}件")
sample_wid = list(hints.keys())[0]
print(f"サンプル({sample_wid}):", hints[sample_wid])
