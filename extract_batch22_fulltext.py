# -*- coding: utf-8 -*-
"""next_batch_ids.json(97件、第22バッチ)について、本文25%(下限300字・上限4,000字)版と
全文版を抽出する。batch1〜5と同じ手法(body_parser.pyの下請け関数使用)。body_parser.py自体は
変更しない。PIPELINE_V2_SPEC.md 3章に従い、このバッチから切り出しロジックを25%方式に変更。
出力ファイル名(batchN_fulltext_4000.json)は実態と合わなくなるが、gate_check_batch.py等が
参照しているためリネームしない(同仕様書3-2節)。"""
import json
import os
import re
from body_parser import decode_body, slice_sections, clean_ruby_and_notes, to_plain_text

index = json.load(open("index.json", encoding="utf-8"))
works = {w["作品ID"]: w for w in index["作品"]}

ids = json.load(open("next_batch_ids.json", encoding="utf-8"))
print("対象件数:", len(ids))

fulltext_4000 = {}
fulltext_full = {}
meta = {}
errors = {}

for wid in ids:
    w = works.get(wid)
    if w is None:
        errors[wid] = "index.jsonに存在しない"
        continue
    body_url = w.get("本文URL")
    if not body_url:
        errors[wid] = "本文URLが欠損"
        continue
    fname = body_url.rsplit("/", 1)[-1]
    m_dir = re.search(r"/cards/(\d{6})/files/", body_url)
    if not m_dir:
        errors[wid] = f"本文URLから著者ディレクトリを抽出できない: {body_url}"
        continue
    author_id6 = m_dir.group(1)
    path = os.path.join("aozora_src", "cards", author_id6, "files", fname)
    if not os.path.exists(path):
        errors[wid] = f"本文ファイルが見つからない: {path}"
        continue
    try:
        data = open(path, "rb").read()
        raw_text, n_bad = decode_body(data)
        main_html, biblio_html, credit_format = slice_sections(raw_text)
        ruby_stripped_html, ruby_count = clean_ruby_and_notes(main_html)
        full_text = to_plain_text(ruby_stripped_html, strip_headings=False)
    except Exception as e:
        errors[wid] = f"パース失敗: {type(e).__name__}: {e}"
        continue

    if len(full_text) < 200:
        errors[wid] = f"本文が200字未満({len(full_text)}字)"
        continue

    fulltext_full[wid] = full_text
    # PIPELINE_V2_SPEC.md 3-1節: 本文の25%(下限300字・上限4,000字)に変更。
    # 旧: fulltext_4000[wid] = full_text[:4000]
    _cut = min(4000, max(300, int(len(full_text) * 0.25)))
    fulltext_4000[wid] = full_text[:_cut]
    meta[wid] = {
        "作品ID": wid,
        "作品名": w.get("作品名"),
        "著者ID": w.get("著者ID"),
        "文字遣い": w.get("文字遣い"),
        "文字数": len(full_text),
        "本文ファイルパス": path,
        "n_bad_chars": n_bad,
        "credit_format": credit_format,
    }

print("抽出成功:", len(fulltext_full))
print("エラー:", len(errors))
for wid, msg in errors.items():
    print(" ", wid, msg)

json.dump(fulltext_4000, open("batch22_fulltext_4000.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump(fulltext_full, open("batch22_fulltext_full.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump(meta, open("batch22_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(errors, open("batch22_errors.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("保存完了")
