# -*- coding: utf-8 -*-
"""
フェーズ2 第1便 — 案内文の品質ゲート
第三層（固有名詞の実在照合）・第四層（現代語ゲート）・第五層（規格の遵守）をコードとして実装する。
"""
import re
import json
from collections import Counter

# ============================================================
# 第三層：固有名詞の実在照合（第2便・差し戻し対応版）
# ============================================================
# 【第1便からの変更点】
# 第1便は「生成者が使用した固有名詞を自己申告し、それを機械照合する」方式
# だったが、独立検証で「申告を省略すれば同じ嘘が素通りする」ことが判明した
# （偽の「吉原」テストで、吉原を申告しなければ判定OKになってしまう）。
# これはゲートとして成立していない——生成側の善意に依存している。
#
# 対応：自己申告をやめ、janome（形態素解析）による機械抽出に戻す。
# 第1便が自動抽出を諦めた理由（純粋な漢字連・カタカナ連の正規表現抽出だと
# 97篇中84篇が誤検知）は、抽出が素朴すぎたことが原因であり、方式そのもの
# が間違っていたわけではない。品詞情報を使えば、一般語彙（形容動詞語幹・
# サ変接続等）と固有名詞は分離できる。

from janome.tokenizer import Tokenizer as _JanomeTokenizer
_janome_t = _JanomeTokenizer()

KANJI_RUN_RE = re.compile(r'[\u4E00-\u9FFF]{2,}')
KATAKANA_RUN_RE = re.compile(r'[\u30A0-\u30FF\u30FC]{2,}')
KANJI_CHAR_RE = re.compile(r'[\u4E00-\u9FFF]')
KATAKANA_ONLY_RE = re.compile(r'^[\u30A0-\u30FF\u30FC]+$')

# 案内文で頻出する一般語彙（固有名詞ではないので本文照合の対象外とする）。
# 第1便で実際に使った語彙から機械的に収集し、随時追加していく運用を想定。
COMMON_VOCAB = set("""
事件 人生 時間 生活 世界 社会 自然 文学 芸術 家族 友人 先生 学校
仕事 心情 気持 気持ち 記憶 思い出 感情 感想 印象 様子 場面 場所
男性 女性 少女 少年 子供 子ども 老人 夫婦 母親 父親 祖母 祖父
毎日 一日 昨日 今日 明日 季節 季節感 移り変わり 変化 出来事
物語 小説 随筆 評論 詩集 童話 戯曲 作品 冒頭 展開 結末 内容
言葉 表現 文章 文体 説明 描写 比喩 象徴 主題 背景 舞台
自分 相手 二人 三人 誰か 何か 全体 一部 途中 最初 最後 途中経過
現代 当時 過去 未来 現在 歴史 時代 風景 景色 情景 心境 心理
理由 原因 結果 影響 経験 体験 事実 真実 疑問 謎 秘密 予感
死 生 恋 愛 孤独 幼年 幸福 不安 恐怖 喜び 悲しみ 怒り 驚き
科学 現象 自然現象 実験 観察 研究 考察 論理 議論 主張 意見
戦争 平和 政治 経済 教育 宗教 哲学 思想 文化 伝統 習慣 風習
手紙 日記 記録 報告 発表 講演 対話 会話 独白 語り 声
旅行 旅 帰郷 故郷 都会 田舎 都市 農村 港 駅 道 橋 川 山 海
朝 昼 夜 夕方 早朝 深夜 季節風 雨 雪 風 雷 嵐 台風 霧 雲 星 月 太陽
仲間 隣人 恩人 敵 味方 主人公 語り手 登場人物 作者 著者 筆者
仕草 表情 動作 行動 態度 性格 人柄 人物像 存在 姿 影
書き手 立ち位置 話題 出来事 展開 導入 発端 起点 きっかけ
""".split())

# 一般的なカタカナ外来語（固有名詞ではない）
COMMON_KATAKANA = set("""
メートル キロ センチ ミリ グラム リットル ページ ノート カード
ホテル レストラン バス タクシー ラジオ テレビ カメラ ガラス
コーヒー パン ビール ワイン チーズ ケーキ アルコール
イメージ メッセージ エネルギー システム パターン イメージ
テーマ タイトル シーン シリーズ ジャンル タイプ レベル
""".split())


# 旧字体のうち、辞書に単独の固有名詞として登録されておらず、かつ未知語処理でも
# 分解されない（＝1文字ずつのフラグメント化にも引っかからない）ケースがある
# （実例：「豐太郎」は「太田」＋「豐太郎」に分割されるが、後者は
# 名詞,一般 の1トークンとして丸ごと確定してしまい、本抽出のどの規則にも
# 引っかからない）。この穴を完全に塞ぐことはできないが、既知の旧字体を
# 含むトークンを追加候補として拾うことで、既知の範囲はカバーする。
# 【既知の限界】このリストにない旧字体・当て字は依然として見逃す（8章参照）。
KYUJITAI_CHARS = set("豐龍澤邊齋當體對應櫻圓國學實驗殘藝萬離靈廣澁鐵藏")


def extract_proper_noun_candidates_janome(guide_text: str):
    """janomeの品詞情報を使い、固有名詞候補を機械抽出する（第2便で採用）。

    1. 固有名詞タグの付いたトークン（連続する場合は連結）
    2. 1文字の名詞トークンが2つ以上連続する箇所（辞書にない語が
       未知語処理で1文字ずつに分解された痕跡。例：龍華寺→龍/華/寺）
    3. カタカナのみからなるトークン（辞書にない外国人名等は、未知語処理で
       1トークンのまま「名詞,一般」に誤タグされる。例：アクーリナ）。
       ただし一般的な外来語（COMMON_KATAKANA）は除く
    4. 既知の旧字体文字を含む「名詞」トークン（上記コメント参照。
       未知語処理の穴を部分的に補うbest-effort。8章の既知の限界を参照）
    の和集合を返す。自己申告には一切依存しない。
    """
    tokens = list(_janome_t.tokenize(guide_text))
    candidates = []

    # (1) 固有名詞タグの連結
    buf = []
    for tok in tokens:
        pos = tok.part_of_speech.split(',')
        if pos[0] == '名詞' and pos[1] == '固有名詞':
            buf.append(tok.surface)
        else:
            if buf:
                candidates.append(''.join(buf))
                buf = []
    if buf:
        candidates.append(''.join(buf))

    # (2) 1文字名詞の連続（未知語の文字単位フラグメント化）
    # 【構造的な除外】数詞（一二三四五六七八九十百千万）で始まる連続は除外する。
    # 「一本」「一杯」「七人」「二重丸」のような数詞+助数詞の表現が、未知語の
    # フラグメント化と誤って合流するケースが実際に頻発したため（13件中7件）。
    # これは個別の語を許容リストに足す対症療法ではなく、「本物の固有名詞は
    # このルート（未知語フラグメント化）では、数詞1文字から始まる形をまず
    # 取らない」という構造的な性質に基づく除外である。数詞を含む本物の固有
    # 名詞（例：三田、九段）は、janomeの辞書に登録済みで固有名詞タグ（1番の
    # 経路）が付くため、この除外の影響を受けない。
    KANJI_NUMERALS = set("一二三四五六七八九十百千万")
    frag = []
    for tok in tokens:
        pos = tok.part_of_speech.split(',')
        is_single_kanji_noun = (
            pos[0] == '名詞' and len(tok.surface) == 1
            and KANJI_CHAR_RE.match(tok.surface) is not None
        )
        if is_single_kanji_noun:
            frag.append(tok.surface)
        else:
            if len(frag) >= 2 and frag[0] not in KANJI_NUMERALS:
                candidates.append(''.join(frag))
            frag = []
    if len(frag) >= 2 and frag[0] not in KANJI_NUMERALS:
        candidates.append(''.join(frag))

    # (3) カタカナのみのトークン（未知の外国人名等）
    for tok in tokens:
        s = tok.surface
        if len(s) >= 2 and KATAKANA_ONLY_RE.match(s) and s not in COMMON_KATAKANA:
            candidates.append(s)

    # (4) 既知の旧字体を含む「名詞」トークン（best-effort）
    for tok in tokens:
        pos = tok.part_of_speech.split(',')
        if pos[0] == '名詞' and any(ch in KYUJITAI_CHARS for ch in tok.surface):
            candidates.append(tok.surface)

    seen = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def extract_proper_noun_candidates(guide_text: str):
    """案内文から固有名詞候補（一般語彙を除いた漢字連・カタカナ連）を抽出する。"""
    candidates = []
    for m in KANJI_RUN_RE.finditer(guide_text):
        tok = m.group()
        # 一般語彙に完全一致する場合は除外。
        # 長い語の場合、一般語彙の組み合わせである可能性があるので、
        # 2文字ずつの部分列も一般語彙にすべて分解できるなら除外する。
        if tok in COMMON_VOCAB:
            continue
        if _decomposable_into_common_vocab(tok):
            continue
        candidates.append(tok)
    for m in KATAKANA_RUN_RE.finditer(guide_text):
        tok = m.group()
        if tok in COMMON_KATAKANA:
            continue
        candidates.append(tok)
    return candidates


def _decomposable_into_common_vocab(tok: str) -> bool:
    """4文字以上の漢字連が、一般語彙2つの単純な連結として分解できるかを試す
    （例：「毎日」＋「生活」→「毎日生活」のような組み合わせを誤検知しないため）。"""
    n = len(tok)
    if n < 4:
        return False
    for i in range(2, n - 1):
        if tok[:i] in COMMON_VOCAB and _decomposable_into_common_vocab_or_common(tok[i:]):
            return True
    return False


def _decomposable_into_common_vocab_or_common(tok: str) -> bool:
    if tok in COMMON_VOCAB:
        return True
    return _decomposable_into_common_vocab(tok)


def check_proper_nouns_exist(guide_text: str, source_fulltext: str, declared_nouns=None):
    """第三層：固有名詞候補が本文に実在するかを照合する（第2便版）。

    【重要】declared_nouns（生成側の自己申告）は、この便からは判定に使わない。
    独立検証で「申告を省略すれば同じ嘘が素通りする」ことが判明したため
    （PHASE2_DELIVERY2_SPEC.md 1章）、自己申告への依存を廃止し、
    janomeによる機械抽出（extract_proper_noun_candidates_janome）を
    唯一の抽出経路とする。declared_nouns は下位互換のため引数として
    残すが、無視する（意図的な仕様）。
    """
    candidates = extract_proper_noun_candidates_janome(guide_text)

    missing = [c for c in candidates if c not in source_fulltext]
    return {
        "候補": candidates,
        "本文に不在": missing,
        "判定": "OK" if not missing else "NG",
    }


# ============================================================
# 第四層：現代語ゲート
# ============================================================
# 常用漢字表だけでは「麦酒」（漢字自体は常用）のような語を捕まえられないため、
# 実際に試作で混入した語＋文語期の文学に頻出する非流通語のブラックリストを持つ。
ARCHAIC_VOCAB = set("""
廓 楼上 麦酒 従僕 逢引 逢引き 下人 頸 凶事 妾 下女 書生 人力車
女中 車夫 番頭 丁稚 手代 御新造 御新造さん 御新造様 内儀 内儀さん
遊女 娼妓 女郎 廓者 揚屋 置屋 芸妓 巫女 神官 侍女 乳母 傅育
候 候補（者） 御座候 参らせ候 仕り候 相成候 罷り越し 罷り在り
給仕 小者 中間 供侍 供廻り 家扶 家令 執事見習い 女房詞
""".split())


def check_modern_vocabulary(guide_text: str):
    """第四層：案内文に非流通語（古語・死語）が混入していないか。"""
    hits = [w for w in ARCHAIC_VOCAB if w in guide_text]
    return {
        "混入語": hits,
        "判定": "OK" if not hits else "NG",
    }


# ============================================================
# 第五層：規格の遵守
# ============================================================
RANKING_WORDS = ["傑作", "名作", "代表作", "不朽の", "珠玉の", "必読",
                  "色褪せない", "普遍的な", "後世に残る", "金字塔"]

# 結末を明示してしまっている疑いのある表現（構造的対策＝入力4000字制限が主で、
# これは補助的な検出に過ぎない）
ENDING_HINT_WORDS = ["最後には", "結局", "ついに死", "自殺する", "命を落とす",
                      "結ばれる", "結末", "オチ"]


def check_length(guide_text: str, lo=60, hi=100):
    n = len(guide_text)
    return {"文字数": n, "判定": "OK" if lo <= n <= hi else "NG"}


def check_no_ranking_words(guide_text: str):
    hits = [w for w in RANKING_WORDS if w in guide_text]
    return {"評価語": hits, "判定": "OK" if not hits else "NG"}


def check_no_ending_hints(guide_text: str):
    hits = [w for w in ENDING_HINT_WORDS if w in guide_text]
    return {"結末示唆語": hits, "判定": "OK" if not hits else "NG"}


def check_ending_diversity(guide_texts: dict, threshold_ratio=0.2, tail_len=4):
    """【旧版・互換のため残置】複数篇の文末（末尾tail_len文字）の分布を見る。

    第1便はこの表層4文字グルーピングで「OK」と報告したが、独立検証で
    「る随筆。」「く随筆。」「す随筆。」等、直前1文字の違いにより同一の
    実質的パターンが分散して数えられ、実際には20%を超えていたことが
    判明した（完了条件5が実は未達だった）。この関数は下位互換のために
    残すが、判定には check_ending_diversity_v2 を使うこと。
    """
    tails = [gt[-tail_len:] for gt in guide_texts.values()]
    c = Counter(tails)
    n = len(tails)
    over = {t: cnt for t, cnt in c.items() if cnt / n > threshold_ratio}
    return {
        "分布": dict(c.most_common()),
        "件数": n,
        "閾値超過": over,
        "判定": "OK" if not over else "NG",
    }


# 文末が名詞（形式名詞）で終わっている場合、その名詞を丸ごと1つのパターンとして
# 数える（「〜る随筆。」「〜く随筆。」を「随筆」という同一パターンにまとめる）。
FORM_NOUN_RE = re.compile(
    r'(随筆|評論|小品|追想|書評|文芸評|論考|追悼文|紀行文|序文|提案文|脚本|物語|連作詩|詩|読み物|遺稿)。$'
)
# 用言終止の場合は、活用語尾を正規化して「基本パターン」でまとめる
# （「〜ている。」「〜ていく。」等、動詞の活用形の違いをそのまま数えると
#  第1便と同じ轍を踏む。ここでは終止形の種類そのもので束ねる）。
VERB_ENDING_PATTERNS = [
    ("ている。", re.compile(r'ている。$')),
    ("ていく。", re.compile(r'ていく。$')),
    ("ていた。", re.compile(r'ていた。$')),
    ("てくる。", re.compile(r'てくる。$')),
    ("始める。", re.compile(r'始める。$')),
    ("続ける。", re.compile(r'続ける。$')),
    ("しまう。", re.compile(r'しまう。$')),
    ("とする。", re.compile(r'とする。$')),
]


def check_ending_diversity_v2(guide_texts: dict, threshold_ratio=0.2):
    """文末を「形式名詞終止」と「用言終止」の2軸でグルーピングし直し、
    どちらの軸でも単一パターンが threshold_ratio を超えないことを確認する
    （PHASE2_DELIVERY2_SPEC.md 2章、差し戻し対応）。"""
    n = len(guide_texts)
    form_counts = Counter()
    verb_counts = Counter()
    other = 0
    for gt in guide_texts.values():
        m = FORM_NOUN_RE.search(gt)
        if m:
            form_counts[m.group(1)] += 1
            continue
        matched = False
        for label, pat in VERB_ENDING_PATTERNS:
            if pat.search(gt):
                verb_counts[label] += 1
                matched = True
                break
        if not matched:
            other += 1

    form_over = {k: v for k, v in form_counts.items() if v / n > threshold_ratio}
    verb_over = {k: v for k, v in verb_counts.items() if v / n > threshold_ratio}

    return {
        "件数": n,
        "形式名詞終止の分布": dict(form_counts.most_common()),
        "形式名詞終止_合計": sum(form_counts.values()),
        "用言終止の分布": dict(verb_counts.most_common()),
        "用言終止_合計": sum(verb_counts.values()),
        "その他": other,
        "形式名詞軸_閾値超過": form_over,
        "用言軸_閾値超過": verb_over,
        "判定": "OK" if not form_over and not verb_over else "NG",
    }


def run_all_gates(work_id, guide_text, source_fulltext, declared_nouns=None):
    r3 = check_proper_nouns_exist(guide_text, source_fulltext, declared_nouns)
    r4 = check_modern_vocabulary(guide_text)
    r5a = check_length(guide_text)
    r5b = check_no_ranking_words(guide_text)
    r5c = check_no_ending_hints(guide_text)
    overall = "OK" if all(r["判定"] == "OK" for r in (r3, r4, r5a, r5b, r5c)) else "NG"
    return {
        "作品ID": work_id,
        "第三層_固有名詞照合": r3,
        "第四層_現代語ゲート": r4,
        "第五層_文字数": r5a,
        "第五層_評価語": r5b,
        "第五層_結末示唆": r5c,
        "総合判定": overall,
    }


if __name__ == "__main__":
    # --- 検証1：たけくらべに偽の「吉原」を入れた案内文が、第三層に確実に弾かれるか ---
    # 【第2便】自己申告を一切渡さずに検証する（declared_nounsは無視される仕様）。
    fake_takekurabe = "吉原にほど近い町で育つ子供たち。勝気な美登利と、龍華寺の息子・信如。移りゆく季節の祭りの中、二人の間柄も少しずつ形を変えていく。"
    fulltext = json.load(open("fulltext_100.json", encoding="utf-8"))["389"]
    r = check_proper_nouns_exist(fake_takekurabe, fulltext)
    print("=== 検証1：偽『吉原』ケース（自己申告なし・機械抽出のみ） ===")
    print(json.dumps(r, ensure_ascii=False, indent=1))
    assert r["判定"] == "NG" and "吉原" in r["本文に不在"], "吉原が弾かれていない！"
    print("[OK] 偽『吉原』は自己申告なしでも確実に弾かれた\n")

    # --- 検証1b：正しい案内文（大音寺前）は通ることの確認 ---
    real_takekurabe = "大音寺前、遊郭の近くで育つ子供たち。勝気な美登利と、龍華寺の息子・信如。移りゆく季節の祭りの中、二人の間柄も少しずつ形を変えていく。"
    r_real = check_proper_nouns_exist(real_takekurabe, fulltext)
    print("=== 検証1b：正しい案内文（大音寺前）が通ることの確認 ===")
    print(json.dumps(r_real, ensure_ascii=False, indent=1))
    assert r_real["判定"] == "OK", "正しい案内文が誤って弾かれている！"
    print("[OK] 正しい案内文は通過した\n")

    # --- 検証2：試作で実際に混入した5語がすべて第四層に弾かれるか ---
    print("=== 検証2：非流通語5語の検出 ===")
    test_words = ["廓", "楼上", "麦酒", "従僕", "逢引"]
    for w in test_words:
        sample = f"これは{w}についての文章です。"
        r = check_modern_vocabulary(sample)
        status = "OK" if w in r["混入語"] else "NG（検出漏れ）"
        print(f"[{status}] {w}: {r['混入語']}")
    all_sample = "廓・楼上・麦酒・従僕・逢引のすべてを含む文章。"
    r = check_modern_vocabulary(all_sample)
    assert set(test_words) <= set(r["混入語"]), "5語すべてを検出できていない"
    print("[OK] 5語すべてが同時に検出された")
