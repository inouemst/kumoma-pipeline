# -*- coding: utf-8 -*-
"""
本文XHTMLファイル1件から、本文抽出・ルビ処理・クレジット抽出・機械計測を行う。
"""
import re
import html as htmllib

MAIN_START = '<div class="main_text">'
BIBLIO_START = '<div class="bibliographical_information">'
AFTER_TEXT_START = '<div class="after_text">'  # 翻訳者が自ら公開するCCライセンス作品などで使われる代替形式
NOTATION_START = '<div class="notation_notes">'
CARD_DIV_START = '<div id="card">'

RUBY_TAG_RE = re.compile(r'<ruby>')
RT_RE = re.compile(r'<rt>.*?</rt>', re.S)
RP_RE = re.compile(r'<rp>.*?</rp>', re.S)
RB_OPEN_RE = re.compile(r'<rb>')
RB_CLOSE_RE = re.compile(r'</rb>')
RUBY_OPEN_RE = re.compile(r'<ruby>')
RUBY_CLOSE_RE = re.compile(r'</ruby>')
NOTES_SPAN_RE = re.compile(r'<span class="notes">.*?</span>', re.S)
KUCHU_RE = re.compile(r'［＃[^］]*］')
BR_RE = re.compile(r'<br\s*/?>', re.I)
TAG_RE = re.compile(r'<[^>]+>')
NAKAMIDASHI_RE = re.compile(r'<h\d class="[^"]*midashi[^"]*">.*?</h\d>', re.S)
CHAPTER_MARKER_LINE_RE = re.compile(r'^[一二三四五六七八九十百千0-90-9]{1,6}$')
HEADING_SUSPECT_RE = re.compile(r'^([^\u3000。]{1,12})\u3000(.*)$', re.S)


def opening_sentence_needs_review(sentence: str) -> bool:
    """はじまりの一文の冒頭に、見出しタグを伴わない素のテキストの小見出しが
    混入している疑いがあるかを判定する（第3便・方針Y）。

    自動除去は行わない。理由：同じ「短い語＋全角スペース＋続き」という構造が、
    本物の小見出し混入（例：「戦前の形勢　再度の長州征伐に失敗して…」）と、
    詩の意図的な行分け（例：「あちらの　森の　ほうで、ふくろうが　なきました。」）
    の両方に現れ、機械的に区別できない。削除すると後者のような正常な原文を
    破壊するリスクがあるため、フラグを立てて人手レビューに委ねるにとどめる。
    """
    m = HEADING_SUSPECT_RE.match(sentence)
    if not m:
        return False
    head, rest = m.groups()
    if not head:
        return False
    if head[-1] in '！？、）」』':
        return False  # 既に完結した発話・地の文の一部とみなし、誤検知を減らす
    if rest.startswith(head):
        return False  # 直後に同じ語が繰り返される＝人名等の正常な文の可能性が高い
    return True

KANJI_RE = re.compile(r'[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF]')

# 文語判定用の語尾リスト。実データ（樋口一葉全43作・森鴎外・泉鏡花・幸田露伴 の
# 文末文字頻度）から設計し、こころ・羅生門・蜘蛛の糸・ごん狐・太宰治・芥川の
# 新字旧仮名作品で誤爆が無いことを検証済み（tune_bungo.py 参照）。
#
# 除外した候補とその理由：
#   て／ぬ(裸)／る(裸)／れ(裸)／ん(裸)／なる／なれ
#     → 口語の普通の活用語尾と衝突しやすく、誤爆の主因になる
#   居る／有る／言ふ／云ふ 等、漢字選択に基づく候補
#     → 文語文法ではなく旧仮名（古い表記習慣）との相関に過ぎない。
#       文字遣いメタデータ（旧仮名）と機能的に重複してしまい、
#       「旧仮名と文語は独立した軸」という設計方針に反するため除外
BUNGO_ENDINGS = (
    # き（過去）
    "し", "しか", "き",
    # けり（過去・詠嘆）
    "けり", "ける", "けれ",
    # つ（完了）
    "つ", "つる", "つれ",
    # たり／り（完了・存続）
    "たり", "たる", "たれ", "り",
    # なり（断定）※裸の「なる」「なれ」は誤爆源のため除外
    "なり",
    # べし（推量・当然）
    "べし", "べき", "べく", "べけれ",
    # む（推量・意志）※裸の「ん」は誤爆源のため除外
    "む", "め",
    # らむ／けむ（現在・過去推量）
    "らむ", "らん", "けむ", "けん",
    # ず（打消）
    "ず", "ざり", "ざる", "ざれ", "ぬ",
    # その他の文語標識
    "ごとし", "なし", "あり", "じ", "らし", "めり",
)


class ParseError(Exception):
    pass


def decode_body(data: bytes):
    """Shift_JISでデコード。失敗文字数をログ用に返す。"""
    try:
        text = data.decode('shift_jis')
        return text, 0
    except UnicodeDecodeError:
        pass
    # cp932は shift_jis のスーパーセット。まずこちらを試す。
    try:
        text = data.decode('cp932')
        return text, 0
    except UnicodeDecodeError:
        pass
    # 最終手段：置換して件数を数える
    text = data.decode('shift_jis', errors='replace')
    n_bad = text.count('\ufffd')
    return text, n_bad


def slice_sections(full_text: str):
    i0 = full_text.find(MAIN_START)
    if i0 == -1:
        if full_text.lstrip()[:6].upper() == '<HTML>' or '<HTML>' in full_text[:50].upper():
            raise ParseError("legacy_pre_xhtml_format")
        raise ParseError("main_text not found")

    i1 = full_text.find(BIBLIO_START, i0)
    credit_format = "standard"
    if i1 == -1:
        i1 = full_text.find(AFTER_TEXT_START, i0)
        credit_format = "after_text"
    if i1 == -1:
        raise ParseError("bibliographical_information not found")

    start_tag = BIBLIO_START if credit_format == "standard" else AFTER_TEXT_START
    main_html = full_text[i0 + len(MAIN_START):i1]

    i2 = full_text.find(NOTATION_START, i1)
    if i2 == -1:
        i2 = full_text.find(CARD_DIV_START, i1)
    biblio_html = full_text[i1 + len(start_tag):i2] if i2 != -1 else full_text[i1 + len(start_tag):]

    return main_html, biblio_html, credit_format


def clean_ruby_and_notes(html_fragment: str):
    """ルビ・注記除去。ルビ数（除去前）を合わせて返す。"""
    ruby_count = len(RUBY_TAG_RE.findall(html_fragment))
    s = html_fragment
    s = RT_RE.sub('', s)
    s = RP_RE.sub('', s)
    s = RB_OPEN_RE.sub('', s)
    s = RB_CLOSE_RE.sub('', s)
    s = RUBY_OPEN_RE.sub('', s)
    s = RUBY_CLOSE_RE.sub('', s)
    s = NOTES_SPAN_RE.sub('', s)
    s = KUCHU_RE.sub('', s)
    return s, ruby_count


def to_plain_text(html_fragment: str, strip_headings: bool = False):
    s = html_fragment
    if strip_headings:
        s = NAKAMIDASHI_RE.sub('', s)
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    s = BR_RE.sub('\n', s)
    s = TAG_RE.sub('', s)
    s = htmllib.unescape(s)
    return s


def char_count(text: str) -> int:
    return len(text.replace('\n', '').replace('\r', ''))


def kanji_ratio(text: str, total_chars: int) -> float:
    if total_chars == 0:
        return 0.0
    n_kanji = len(KANJI_RE.findall(text))
    return n_kanji / total_chars


def _depth_annotated_chars(text: str):
    """(文字, その文字を追加する時点でのカギ括弧の深さ) を順に yield する。

    深さは行（＝ <br /> による段落区切り）ごとに0へリセットする。
    日本語の組版では、複数段落にまたがる会話・書簡は各段落の頭に「を
    繰り返すが」は最後の段落にしか付かない。このため文書全体で深さを
    積み上げる方式では、一度対応が崩れると本文全体が「会話の中」として
    汚染される（こころで実測：「707個に対し」652個、差55個）。

    行ごとにリセットすることで、誤りをその行の中に閉じ込める。
    複数行にまたがる会話文の2行目以降を会話文として数え損なう（過小評価）
    という副作用があるが、全文が汚染される事態よりはるかに軽微であるため
    採用する。
    改行文字そのものはyieldしない（改行は文字数・会話文数に含めない）。
    """
    for line in text.split('\n'):
        depth = 0
        for ch in line:
            if ch == '「':
                yield ch, depth
                depth += 1
            elif ch == '」':
                if depth > 0:
                    depth -= 1
                yield ch, depth
            else:
                yield ch, depth


def dialogue_char_count(text: str) -> int:
    """「」内（地の文の外）の文字数。深さは行ごとにリセットする。"""
    count = 0
    for ch, depth in _depth_annotated_chars(text):
        if depth > 0 and ch not in ('「', '」'):
            count += 1
    return count


def dialogue_ratio(text: str, total_chars: int) -> float:
    if total_chars == 0:
        return 0.0
    return dialogue_char_count(text) / total_chars


def split_sentences(text: str):
    """地の文の「。」で文を分割する。カギ括弧の深さは行ごとにリセットする
    （dialogue_char_countと同じ理由。文分割ロジックを共通化することで、
    同じバグを複数箇所に残さない）。

    「。」が一つも見つからない作品では、本文全体を1文として返す。
    """
    sentences = []
    buf = []
    for ch, depth in _depth_annotated_chars(text):
        buf.append(ch)
        if ch == '。' and depth == 0:
            sentences.append(''.join(buf))
            buf = []
    if buf:
        tail = ''.join(buf).strip()
        if tail:
            sentences.append(tail)
    return sentences


def strip_leading_chapter_markers(text: str) -> str:
    """先頭の空行と、章番号のみからなる行（見出しタグを伴わない簡易な章番号表記）を読み飛ばす。"""
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        stripped = lines[i].strip(' \u3000\t')
        if stripped == '':
            i += 1
            continue
        if CHAPTER_MARKER_LINE_RE.match(stripped):
            i += 1
            continue
        break
    return '\n'.join(lines[i:])


MAX_OPENING_LEN = 150


def extract_opening_sentence(text_no_heading: str):
    """地の文（「」の外）の最初の句点までを取り出す。

    150字を超える場合は先頭150字で打ち切る（UI側でフェードアウト表示するための
    上限。前方から切るだけなので原文の語は一切変えていない）。
    「。」が見つからない、または結果が空になる場合は、本文冒頭150字を返す。

    戻り値: (はじまりの一文, 省略したかどうかのbool)
    """
    stripped = strip_leading_chapter_markers(text_no_heading)
    buf = []
    for ch, depth in _depth_annotated_chars(stripped):
        buf.append(ch)
        if ch == '。' and depth == 0:
            break
    sentence = ''.join(buf).strip().lstrip('\u3000 ')

    truncated = False
    if len(sentence) > MAX_OPENING_LEN:
        sentence = sentence[:MAX_OPENING_LEN]
        truncated = True

    if not sentence:
        # 「。」が一つも無い作品、または冒頭が全て見出し・空白だった場合のフォールバック。
        # 章番号除去前のテキストから、改行を除いて先頭MAX_OPENING_LEN字を取る。
        # 指示書通り、このフォールバック経路では省略フラグを常にtrueにする。
        fallback_source = text_no_heading.replace('\n', '').lstrip('\u3000 ')
        sentence = fallback_source[:MAX_OPENING_LEN]
        truncated = True

    return sentence, truncated


def bungo_ratio(text: str) -> float:
    """文末（。の直前、閉じ括弧はスキップ）が文語助動詞で終わる文の比率。"""
    sentences = split_sentences(text)

    if not sentences:
        return 0.0

    n_bungo = 0
    n_checked = 0
    for s in sentences:
        core = s.rstrip('。').rstrip('」』）)')
        if len(core) < 2:
            continue
        n_checked += 1
        if core.endswith(BUNGO_ENDINGS):
            n_bungo += 1
    if n_checked == 0:
        return 0.0
    return n_bungo / n_checked


# --- クレジット抽出 ---

CREDIT_LABELS = ["底本の親本", "底本", "入力校正", "入力", "校正", "初出",
                 "翻訳の底本", "翻訳者"]
LABEL_LINE_RE = re.compile(r'^(' + '|'.join(CREDIT_LABELS) + r')：(.*)$')
DATE_ANNOUNCE_RE = re.compile(r'\d+年\d+月\d+日')
BRACKET_RE = re.compile(r'「([^」]*)」')


def parse_credits(biblio_html: str):
    # <a>タグの中身だけ残してplain textにする（テキストは変えず、タグだけ除去）
    s = biblio_html
    s = BR_RE.sub('\n', s)
    s = TAG_RE.sub('', s)
    s = htmllib.unescape(s)
    lines = [ln.strip() for ln in s.split('\n')]
    lines = [ln for ln in lines if ln and ln != '\ufeff']

    fields = {}  # label -> first-line remainder
    active_label = None
    shoshutsu_extra = None

    for ln in lines:
        m = LABEL_LINE_RE.match(ln)
        if m:
            label, rest = m.groups()
            if label not in fields:
                fields[label] = rest.strip()
            active_label = label
            continue
        # 継続行の扱い：初出のみ、直後1行に限り連結する
        if active_label == "初出" and shoshutsu_extra is None:
            if (ln.startswith('※') or ln.startswith('入力') or ln.startswith('校正')
                    or DATE_ANNOUNCE_RE.search(ln) or ln.startswith('青空文庫') or 'ボランティア' in ln):
                active_label = None
                continue
            shoshutsu_extra = ln
            continue
        active_label = None

    teihon_raw = fields.get("底本") or fields.get("翻訳の底本")
    teihon = None
    if teihon_raw:
        bm = BRACKET_RE.search(teihon_raw)
        teihon = bm.group(1) if bm else teihon_raw.strip() or None

    nyuryoku = fields.get("入力") or fields.get("入力校正")
    kousei = fields.get("校正") or fields.get("入力校正")
    # after_text形式（CCライセンス翻訳）：入力・校正の概念が無く、翻訳者のみが記録される。
    # この場合は入力者・校正者は欠損として扱う（設計通り、無理に埋めない）。
    honyakusha = fields.get("翻訳者")

    shoshutsu = fields.get("初出")
    if shoshutsu is not None and shoshutsu_extra:
        shoshutsu = shoshutsu + shoshutsu_extra
    if shoshutsu:
        shoshutsu = shoshutsu.strip() or None

    return {
        "底本": teihon,
        "入力者": nyuryoku.strip() if nyuryoku else None,
        "校正者": kousei.strip() if kousei else None,
        "初出": shoshutsu,
        "翻訳者クレジット": honyakusha.strip() if honyakusha else None,
    }


def reading_bucket(minutes: int) -> str:
    if minutes <= 5:
        return "5分以内"
    if minutes <= 15:
        return "15分以内"
    if minutes <= 30:
        return "30分以内"
    if minutes <= 60:
        return "1時間以内"
    return "それ以上"


# --- 読解速度モデル（第4便） ---
# これは機械で取れる「事実」ではなく、我々が置いた「仮定」である。
# 文字数は事実、速度は仮定——両者をデータ上はっきり分ける（設計書 第二層の裏返し）。
# 後から係数だけ差し替えられるよう、定数テーブルとして分離する。
BASE_SPEED_BY_MOJIZUKAI = {
    "新字新仮名": 600,
    "新字旧仮名": 450,
    "旧字新仮名": 420,
    "旧字旧仮名": 300,
}
DEFAULT_SPEED = 450  # 「その他」等、上記に無い区分の暫定値
BUNGO_SPEED_MULTIPLIER = 0.7  # 文語体と判定された場合、上記速度にさらに掛ける


def reading_speed(mojizukai: str, is_bungo: bool):
    """(想定読解速度_字毎分, 速度の根拠) を返す。"""
    base = BASE_SPEED_BY_MOJIZUKAI.get(mojizukai, DEFAULT_SPEED)
    reason = mojizukai if mojizukai in BASE_SPEED_BY_MOJIZUKAI else f"{mojizukai}（既定値）"
    if is_bungo:
        speed = round(base * BUNGO_SPEED_MULTIPLIER)
        reason = f"{reason}・文語体"
        return speed, reason
    return base, reason


def process_body_file(path: str, mojizukai: str):
    data = open(path, 'rb').read()
    raw_text, n_bad_chars = decode_body(data)
    main_html, biblio_html, credit_format = slice_sections(raw_text)

    ruby_stripped_html, ruby_count = clean_ruby_and_notes(main_html)

    full_text = to_plain_text(ruby_stripped_html, strip_headings=False)
    opening_text = to_plain_text(ruby_stripped_html, strip_headings=True)

    n_chars = char_count(full_text)
    kanji_r = kanji_ratio(full_text, n_chars)
    dialogue_r = dialogue_ratio(full_text, n_chars)
    ruby_density = (ruby_count / n_chars) if n_chars else 0.0
    opening_sentence, opening_truncated = extract_opening_sentence(opening_text)
    opening_needs_review = opening_sentence_needs_review(opening_sentence)
    bungo_r = bungo_ratio(full_text)
    # 閾値0.15：樋口一葉全43作品（recall93%）＋こころ・羅生門・蜘蛛の糸・ごん狐・
    # 太宰治30作・芥川の新字旧仮名作品20作（誤爆0%）で検証済み。
    # 1作品の値に合わせて決めていない（tune_bungo.py 参照）。
    is_bungo = bungo_r >= 0.15

    speed, speed_reason = reading_speed(mojizukai, is_bungo)
    minutes = round(n_chars / speed) if n_chars else 0
    bucket = reading_bucket(minutes)

    is_kyu_kana = mojizukai.endswith("旧仮名") if mojizukai else False

    credits = parse_credits(biblio_html)

    return {
        "n_chars": n_chars,
        "reading_speed_cpm": speed,
        "reading_speed_reason": speed_reason,
        "reading_minutes": minutes,
        "reading_bucket": bucket,
        "kanji_ratio": round(kanji_r, 4),
        "dialogue_ratio": round(dialogue_r, 4),
        "ruby_density": round(ruby_density, 5),
        "is_kyu_kana": is_kyu_kana,
        "is_bungo": is_bungo,
        "bungo_ratio_raw": round(bungo_r, 4),
        "opening_sentence": opening_sentence,
        "opening_truncated": opening_truncated,
        "opening_needs_review": opening_needs_review,
        "credits": credits,
        "n_bad_chars": n_bad_chars,
        "credit_format": credit_format,
    }
