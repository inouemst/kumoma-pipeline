# -*- coding: utf-8 -*-
"""運営者確認用の案内文レビューページを生成する。
公開サイト(kumoma-site)とは完全に独立した、ローカル閲覧専用のツール。
使い方: python build_review_page.py 16 17 18
"""
import json
import sys
import html as htmlmod

def esc(s):
    return htmlmod.escape(s or "", quote=True)

def load_batch(n):
    prod = json.load(open(f"production_batch{n}.json", encoding="utf-8"))
    meta = json.load(open(f"batch{n}_meta.json", encoding="utf-8"))
    full = json.load(open(f"batch{n}_fulltext_full.json", encoding="utf-8"))
    items = []
    for wid, v in prod.items():
        m = meta.get(wid, {})
        items.append({
            "batch": n,
            "id": wid,
            "title": m.get("作品名", ""),
            "author_id": m.get("著者ID", ""),
            "chars": m.get("文字数", 0),
            "guide": v.get("案内文"),
            "no_guide_reason": v.get("案内文なし理由"),
            "labels": v.get("ラベル", {}),
            "fulltext": full.get(wid, ""),
        })
    return items

def main():
    batch_nums = [int(a) for a in sys.argv[1:]] or [16, 17, 18]
    all_items = []
    for n in batch_nums:
        all_items.extend(load_batch(n))

    exposed = sum(1 for it in all_items if it["chars"] and it["chars"] <= 4000)
    total = len(all_items)

    rows = []
    for it in sorted(all_items, key=lambda x: (x["chars"] or 999999)):
        guide = it["guide"]
        flag = ""
        if it["chars"] and it["chars"] <= 4000:
            flag = '<span class="flag">全文露出</span>'
        labels = it["labels"] or {}
        label_str = " / ".join(
            "・".join(labels.get(k) or []) for k in ["形式", "主題", "読後感", "時代の質感"] if labels.get(k)
        )
        guide_html = esc(guide) if guide else f'<span class="none">（案内文なし: {esc(it["no_guide_reason"])}）</span>'
        rows.append(f"""
<article class="item" data-chars="{it['chars']}" data-batch="{it['batch']}">
  <div class="head">
    <span class="bid">batch{it['batch']} / {esc(it['id'])}</span>
    <span class="ttl">{esc(it['title'])}</span>
    <span class="chars">{it['chars']:,}字</span>
    {flag}
  </div>
  <div class="guide">{guide_html}</div>
  <div class="labelrow">{esc(label_str)}</div>
  <button class="toggle" onclick="this.nextElementSibling.classList.toggle('open');this.textContent=this.textContent==='本文を見る▾'?'本文を閉じる▴':'本文を見る▾'">本文を見る▾</button>
  <div class="fulltext">{esc(it['fulltext'])}</div>
</article>""")

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>案内文レビュー（内部確認用・非公開）</title>
<style>
:root{{
  --sumi:#22262E; --kumori:#F4F6F8; --kasumi:#DFE4EA; --usu:#EDF0F4; --ma:#7C8697;
  --warn:#B4482A;
  --serif:"Hiragino Mincho ProN","Yu Mincho",YuMincho,"Noto Serif JP",serif;
  --sans:"Hiragino Sans","Hiragino Kaku Gothic ProN","Yu Gothic",YuGothic,"Noto Sans JP",system-ui,sans-serif;
}}
*{{box-sizing:border-box}}
body{{background:var(--kumori);color:var(--sumi);font-family:var(--sans);font-size:14px;line-height:1.7;margin:0}}
.wrap{{max-width:820px;margin:0 auto;padding:24px 20px 96px}}
.banner{{background:#3A2A1A;color:#F5E6D3;font-size:12px;padding:10px 16px;border-radius:2px;margin-bottom:20px;letter-spacing:.05em}}
h1{{font-size:16px;margin:0 0 6px}}
.summary{{font-size:13px;color:var(--ma);margin-bottom:20px;padding:14px 16px;background:#fff;border:1px solid var(--kasumi);border-radius:2px}}
.summary b{{color:var(--warn)}}
.controls{{display:flex;gap:10px;margin-bottom:18px;font-size:12.5px;flex-wrap:wrap}}
.controls button{{padding:6px 12px;border:1px solid var(--kasumi);background:#fff;border-radius:2px;cursor:pointer;font-family:var(--sans)}}
.controls button.active{{background:var(--sumi);color:#fff;border-color:var(--sumi)}}
.item{{background:#fff;border:1px solid var(--kasumi);border-radius:2px;padding:14px 16px;margin-bottom:10px}}
.item.dim{{display:none}}
.head{{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;font-size:12px;color:var(--ma);margin-bottom:8px}}
.head .ttl{{font-family:var(--serif);font-size:15px;color:var(--sumi);font-weight:400}}
.head .chars{{margin-left:auto}}
.flag{{background:var(--warn);color:#fff;font-size:10.5px;padding:2px 7px;border-radius:2px;letter-spacing:.05em}}
.guide{{font-family:var(--serif);font-size:15px;line-height:1.9;padding:10px 12px;background:var(--usu);border-radius:2px;margin-bottom:8px}}
.guide .none{{color:var(--ma);font-family:var(--sans);font-size:13px}}
.labelrow{{font-size:11.5px;color:var(--ma);margin-bottom:8px}}
.toggle{{font-size:11.5px;color:var(--ma);background:none;border:1px solid var(--kasumi);border-radius:2px;padding:4px 10px;cursor:pointer;font-family:var(--sans)}}
.fulltext{{display:none;margin-top:10px;padding:12px 14px;background:#FAFBFC;border:1px dashed var(--kasumi);border-radius:2px;white-space:pre-wrap;font-size:13px;line-height:1.9;max-height:420px;overflow-y:auto}}
.fulltext.open{{display:block}}
</style>
</head>
<body>
<div class="wrap">
<div class="banner">これは運営者確認用の内部ツールです。公開サイト（kumoma-site）とは無関係で、どこにも公開されていません。</div>
<h1>案内文レビュー — batch {', '.join(str(n) for n in batch_nums)}</h1>
<div class="summary">
  全{total}件のうち、<b>{exposed}件（{exposed/total*100:.0f}%）は文字数4000字以下</b> — つまり
  「冒頭4000字だけを見せる」という結末隠しの仕組みが機能せず、本文全体が生成の材料になっています。
  「全文露出」タグがついた項目は、本文全体を確認したうえで案内文を読んでください。
</div>
<div class="controls">
  <button onclick="filterAll()" class="active" id="btn-all">すべて表示（{total}件）</button>
  <button onclick="filterExposed()" id="btn-exposed">全文露出のみ（{exposed}件）</button>
  <button onclick="sortByChars()">文字数が少ない順</button>
</div>
<div id="list">
{''.join(rows)}
</div>
</div>
<script>
function filterAll(){{
  document.querySelectorAll('.item').forEach(el=>el.classList.remove('dim'));
  document.getElementById('btn-all').classList.add('active');
  document.getElementById('btn-exposed').classList.remove('active');
}}
function filterExposed(){{
  document.querySelectorAll('.item').forEach(el=>{{
    const has = el.querySelector('.flag');
    el.classList.toggle('dim', !has);
  }});
  document.getElementById('btn-exposed').classList.add('active');
  document.getElementById('btn-all').classList.remove('active');
}}
function sortByChars(){{
  const list = document.getElementById('list');
  const items = Array.from(list.children);
  items.sort((a,b)=>(+a.dataset.chars)-(+b.dataset.chars));
  items.forEach(el=>list.appendChild(el));
}}
</script>
</body>
</html>"""
    out_path = "review_page.html"
    open(out_path, "w", encoding="utf-8").write(html)
    print(f"生成完了: {out_path} ({total}件、全文露出{exposed}件)")

if __name__ == "__main__":
    main()
