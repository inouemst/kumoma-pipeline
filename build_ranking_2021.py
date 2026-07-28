# -*- coding: utf-8 -*-
"""2021年ランキング上位150件のIDから、まだ使っていない新規のものだけを
ranking_2021_new.json として作る(日本語タイトル・著者はindex.jsonから補う)。"""
import json
import glob

ids_2021_top150 = [
45630,1567,624,127,773,2093,456,789,799,46605,43754,92,776,752,301,424,975,473,47061,277,
2078,462,1058,46817,427,691,637,46268,46669,859,42,832,1565,18376,466,228,275,628,100,56642,
42939,470,2381,45761,43016,60,43873,43737,816,170,2288,52504,42773,59532,1317,794,522,1465,45245,
56648,98,4527,270,58093,56866,56641,894,2285,389,57347,42767,54372,42618,935,772,974,49866,57443,
1924,1504,43752,360,42620,55,1669,179,44909,40,635,19,24454,57320,472,1935,621,42376,42934,622,
43037,59951,211,57228,43015,689,158,56698,20,206,2710,52348,307,57858,51034,1279,55665,1939,4306,
329,4803,2317,496,2302,45679,57190,18335,3391,43017,14,308,521,1084,56143,1869,236,1502,1508,3646,
57849,682,2282,1737,1746,42309,56650,1607,51732,459,761,42308,95
]
ids_2021_top150 = [str(i) for i in ids_2021_top150]

index = json.load(open("index.json", encoding="utf-8"))
works = {w["作品ID"]: w for w in index["作品"]}

already_known = set()
for fn in glob.glob("ranking_*.json"):
    for rank, title, author, wid in json.load(open(fn, encoding="utf-8")):
        already_known.add(wid)

new_ids = [i for i in ids_2021_top150 if i not in already_known]
print(f"2021年上位150件中、新規: {len(new_ids)}件")

out = []
missing = []
for i, wid in enumerate(new_ids, start=1):
    w = works.get(wid)
    if not w:
        missing.append(wid)
        continue
    out.append([str(i), w["作品名"], w["著者"], wid])

if missing:
    print("index.jsonに見つからないID:", missing)

json.dump(out, open("ranking_2021_new.json", "w", encoding="utf-8"), ensure_ascii=False)
print("ranking_2021_new.json に保存:", len(out), "件")
