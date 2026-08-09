# -*- coding: utf-8 -*-
"""遡及調査用レビューページを生成する（GUIDE_TEXT_SPEC_V2.md 4-2節）。
全18バッチを対象に、露出率(min(4000,文字数)/文字数)を計算し、
物語系(小説/童話/戯曲/脚本)を対象に段階分けして表示する。
公開サイトとは独立したローカル閲覧・内部確認用ツール。
使い方: python build_retro_review.py
"""
import json
import glob
import re
import html as htmlmod

NARRATIVE_FORMS = {"小説", "童話", "戯曲", "脚本"}

def esc(s):
    return htmlmod.escape(s or "", quote=True)

def load_authors():
    d = json.load(open("authors.json", encoding="utf-8"))
    au_list = d.get("著者") or []
    return {a.get("著者ID"): a.get("著者名") for a in au_list}

def stage_of(rate):
    if rate >= 0.9:
        return 1
    if rate >= 0.6:
        return 2
    if rate >= 0.4:
        return 3
    return 0  # 対象外(良好域)

def main():
    authors = load_authors()
    batch_nums = []
    for f in sorted(glob.glob("batch*_meta.json")):
        m = re.search(r"batch(\d+)_meta\.json", f)
        if m:
            batch_nums.append(int(m.group(1)))
    batch_nums.sort()

    items = []
    for n in batch_nums:
        try:
            meta = json.load(open(f"batch{n}_meta.json", encoding="utf-8"))
            prod = json.load(open(f"production_batch{n}.json", encoding="utf-8"))
            full = json.load(open(f"batch{n}_fulltext_full.json", encoding="utf-8"))
        except FileNotFoundError:
            continue
        for wid, v in prod.items():
            m = meta.get(wid, {})
            chars = m.get("文字数", 0)
            if not chars:
                continue
            exposed_chars = min(4000, chars)
            rate = exposed_chars / chars
            labels = v.get("ラベル", {}) or {}
            forms = labels.get("形式") or []
            is_narrative = bool(set(forms) & NARRATIVE_FORMS)
            items.append({
                "batch": n,
                "id": wid,
                "title": m.get("作品名", ""),
                "author": authors.get(m.get("著者ID"), m.get("著者ID", "")),
                "chars": chars,
                "exposed_chars": exposed_chars,
                "rate": rate,
                "stage": stage_of(rate),
                "narrative": is_narrative,
                "forms": forms,
                "guide": v.get("案内文"),
                "no_guide_reason": v.get("案内文なし理由"),
                "fulltext": full.get(wid, ""),
            })

    total = len(items)
    narrative_items = [it for it in items if it["narrative"]]
    stage_counts = {1: 0, 2: 0, 3: 0}
    for it in narrative_items:
        if it["stage"] in stage_counts:
            stage_counts[it["stage"]] += 1

    # 露出率の高い順（物語系を優先し、その中で露出率降順。非物語系は末尾）
    items.sort(key=lambda x: (not x["narrative"], -x["rate"]))

    # ファイルサイズ対策：全文埋め込みは、実際にレビュー対象となる
    # 「物語系・第1〜3段階（露出率40%以上）」の464件相当に限定する。
    # 対象外（露出率40%未満・非物語系）まで含めると、数十万字級の長編が
    # 混在してファイルが肥大化する（実測: 全件埋め込みで135MB→GitHubの
    # 単一ファイル上限100MBを超えてpush不可）。対象外は案内文とメタ情報のみ表示。
    rows = []
    for it in items:
        guide = it["guide"]
        guide_html = esc(guide) if guide else f'<span class="none">（案内文なし: {esc(it["no_guide_reason"])}）</span>'
        stage_badge = ""
        needs_fulltext = it["narrative"] and it["stage"] in (1, 2, 3)
        if needs_fulltext:
            stage_badge = f'<span class="stage stage{it["stage"]}">第{it["stage"]}段階</span>'
        narr_badge = '<span class="narr">物語系</span>' if it["narrative"] else '<span class="nonnarr">非物語系</span>'
        if needs_fulltext:
            toggle_html = f'''<button class="toggle" onclick="this.nextElementSibling.classList.toggle('open');this.textContent=this.textContent==='本文を見る▾'?'本文を閉じる▴':'本文を見る▾'">本文を見る▾</button>
  <div class="fulltext">{esc(it['fulltext'])}</div>'''
        else:
            toggle_html = '<div class="notarget">対象外のため本文は非表示（露出率40%未満、または非物語系）</div>'
        rows.append(f"""
<article class="item" data-rate="{it['rate']:.4f}" data-stage="{it['stage']}" data-narrative="{'1' if it['narrative'] else '0'}" data-batch="{it['batch']}">
  <div class="head">
    <span class="bid">batch{it['batch']} / {esc(it['id'])}</span>
    <span class="ttl">{esc(it['title'])}</span>
    <span class="author">{esc(it['author'])}</span>
    {narr_badge}
    {stage_badge}
    <span class="rate">露出率 {it['rate']*100:.0f}%</span>
    <span class="chars">{it['chars']:,}字中{it['exposed_chars']:,}字</span>
  </div>
  <div class="guide">{guide_html}</div>
  {toggle_html}
</article>""")

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>遡及調査レビュー（内部確認用・非公開）</title>
<style>
:root{{
  --sumi:#22262E; --kumori:#F4F6F8; --kasumi:#DFE4EA; --usu:#EDF0F4; --ma:#7C8697;
  --s1:#B4482A; --s2:#B4832A; --s3:#8A8A2A; --narr:#2C6E9B;
  --serif:"Hiragino Mincho ProN","Yu Mincho",YuMincho,"Noto Serif JP",serif;
  --sans:"Hiragino Sans","Hiragino Kaku Gothic ProN","Yu Gothic",YuGothic,"Noto Sans JP",system-ui,sans-serif;
}}
*{{box-sizing:border-box}}
body{{background:var(--kumori);color:var(--sumi);font-family:var(--sans);font-size:14px;line-height:1.7;margin:0}}
.wrap{{max-width:860px;margin:0 auto;padding:24px 20px 96px}}
.banner{{background:#3A2A1A;color:#F5E6D3;font-size:12px;padding:10px 16px;border-radius:2px;margin-bottom:20px;letter-spacing:.05em}}
h1{{font-size:16px;margin:0 0 6px}}
.summary{{font-size:13px;color:var(--ma);margin-bottom:20px;padding:14px 16px;background:#fff;border:1px solid var(--kasumi);border-radius:2px}}
.summary table{{width:100%;border-collapse:collapse;margin-top:8px;font-size:12.5px}}
.summary td{{padding:4px 8px;border-bottom:1px dotted var(--kasumi)}}
.summary td.n{{text-align:right;font-variant-numeric:tabular-nums;color:var(--sumi);font-weight:600}}
.controls{{display:flex;gap:8px;margin-bottom:18px;font-size:12px;flex-wrap:wrap}}
.controls button{{padding:6px 11px;border:1px solid var(--kasumi);background:#fff;border-radius:2px;cursor:pointer;font-family:var(--sans)}}
.controls button.active{{background:var(--sumi);color:#fff;border-color:var(--sumi)}}
.item{{background:#fff;border:1px solid var(--kasumi);border-radius:2px;padding:14px 16px;margin-bottom:10px}}
.item.dim{{display:none}}
.head{{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;font-size:11.5px;color:var(--ma);margin-bottom:8px}}
.head .ttl{{font-family:var(--serif);font-size:15px;color:var(--sumi);font-weight:400}}
.head .author{{color:var(--ma)}}
.head .rate{{margin-left:auto;font-variant-numeric:tabular-nums;font-weight:600;color:var(--sumi)}}
.narr{{background:var(--narr);color:#fff;font-size:10px;padding:1px 6px;border-radius:2px}}
.nonnarr{{background:var(--usu);color:var(--ma);font-size:10px;padding:1px 6px;border-radius:2px}}
.stage{{color:#fff;font-size:10px;padding:1px 6px;border-radius:2px;font-weight:600}}
.stage1{{background:var(--s1)}}
.stage2{{background:var(--s2)}}
.stage3{{background:var(--s3)}}
.guide{{font-family:var(--serif);font-size:15px;line-height:1.9;padding:10px 12px;background:var(--usu);border-radius:2px;margin-bottom:8px}}
.guide .none{{color:var(--ma);font-family:var(--sans);font-size:13px}}
.toggle{{font-size:11.5px;color:var(--ma);background:none;border:1px solid var(--kasumi);border-radius:2px;padding:4px 10px;cursor:pointer;font-family:var(--sans)}}
.fulltext{{display:none;margin-top:10px;padding:12px 14px;background:#FAFBFC;border:1px dashed var(--kasumi);border-radius:2px;white-space:pre-wrap;font-size:13px;line-height:1.9;max-height:420px;overflow-y:auto}}
.fulltext.open{{display:block}}
.notarget{{font-size:11.5px;color:var(--ma);font-style:italic}}
</style>
</head>
<body>
<div class="wrap">
<div class="banner">これは運営者確認用の内部ツールです。公開サイト（kumoma-site）とは無関係で、どこにも公開されていません。GUIDE_TEXT_SPEC_V2.md 4章の遡及調査に対応。</div>
<h1>遡及調査レビュー — 全{len(batch_nums)}バッチ（batch{batch_nums[0]}〜{batch_nums[-1]}）</h1>
<div class="summary">
  対象総数 {total}件（うち物語系 {len(narrative_items)}件）。露出率＝min(4000,文字数)÷文字数。
  <table>
    <tr><td>第1段階（露出率90%以上・最優先）</td><td class="n">{stage_counts[1]}件</td></tr>
    <tr><td>第2段階（露出率60〜90%）</td><td class="n">{stage_counts[2]}件</td></tr>
    <tr><td>第3段階（露出率40〜60%）</td><td class="n">{stage_counts[3]}件</td></tr>
    <tr><td>対象外（露出率40%未満・実地確認で良好域）</td><td class="n">{len(narrative_items)-sum(stage_counts.values())}件</td></tr>
  </table>
</div>
<div class="controls">
  <button onclick="filterStage(0)" class="active" id="btn-0">すべて</button>
  <button onclick="filterStage(1)" id="btn-1">第1段階のみ（{stage_counts[1]}件）</button>
  <button onclick="filterStage(2)" id="btn-2">第2段階のみ（{stage_counts[2]}件）</button>
  <button onclick="filterStage(3)" id="btn-3">第3段階のみ（{stage_counts[3]}件）</button>
  <button onclick="filterNarrOnly()" id="btn-narr">物語系のみ</button>
</div>
<div id="list">
{''.join(rows)}
</div>
</div>
<script>
let narrOnly = false;
let curStage = 0;
function apply(){{
  document.querySelectorAll('.item').forEach(el=>{{
    const stage = +el.dataset.stage;
    const narr = el.dataset.narrative === '1';
    let show = true;
    if(curStage !== 0) show = show && (narr && stage === curStage);
    if(narrOnly) show = show && narr;
    el.classList.toggle('dim', !show);
  }});
}}
function filterStage(n){{
  curStage = n;
  [0,1,2,3].forEach(i=>document.getElementById('btn-'+i).classList.toggle('active', i===n));
  apply();
}}
function filterNarrOnly(){{
  narrOnly = !narrOnly;
  document.getElementById('btn-narr').classList.toggle('active', narrOnly);
  apply();
}}
</script>
</body>
</html>"""
    open("review_retro.html", "w", encoding="utf-8").write(html)
    print(f"生成完了: review_retro.html")
    print(f"総数 {total}件（物語系 {len(narrative_items)}件）")
    print(f"第1段階: {stage_counts[1]}件 / 第2段階: {stage_counts[2]}件 / 第3段階: {stage_counts[3]}件")

if __name__ == "__main__":
    main()
