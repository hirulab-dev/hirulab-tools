#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「文字数カウンタ」の検証(2026-09-01 未明 新設)。

2本目の道具(2026-08-15 公開)なのに検証スクリプトが1本も無かった。
page-contrast(8/31未明)・diff(8/31朝)・json(8/31昼)・unit(8/31夜)に続いて、
**古い道具ほど検証が薄い**という穴を後ろから埋めていく5本目。

★参照の出どころを分ける(1つの参照だけだと、同じ勘違いを2回するので):

  (1) **X の重み付きカウント = twitter-text の公開設定 v3 を Python に書き下したもの**
      これがこの道具の看板機能で、いちばん外しやすいところ。
      設定の中身(公開されている値):
        - 上限 280 / 目盛 100 / 既定の重み 200(=2)
        - 重み 100(=1) の符号位置の範囲: 0–4351 / 8192–8205 / 8208–8223 / 8242–8247
        - URL は長さによらず 23
        - 絵文字は**書記素クラスタ1つで2**(修飾子・ZWJ・国旗をつないでも増えない)
      ★**「全角なら2」ではない**。ベトナム語(U+1EBF など)・… (U+2026)・€ (U+20AC)・
        矢印・数学記号は半角の見た目でも 2 と数えられる。

  (2) **書記素クラスタの切り方は第三者の `regex` モジュール(UAX #29 の `\\X`)**
      道具側はブラウザの `Intl.Segmenter`(ICU)。**別々の実装で同じ切れ方になるか**を見る。

  (3) **空白の集合は ECMAScript の規定を Unicode データ(`unicodedata`)から組み立てる**
      JS の `\\s` は Python の `str.isspace()` と**違う**(U+0085 は Python だけ、
      U+FEFF は JS だけ)。道具は `\\s` を使うので、規定どおりに書き下したものと比べる。

  (4) **残りの数え上げ(文字数・行数・段落数・英単語数・原稿用紙・読了時間)は
      Python で独立に書き下した規則**。第三者ではないが、JS と Python が別々に書いて
      一致するかは見られる。⚠ `Math.round` は 0.5 を上に、Python の `round` は
      偶数に丸めるので、参照側は `floor(x+0.5)` で書く。

  (5) **画面に出た文字列から数に戻す(表示の可逆)**。桁区切りをほどいて元の値になるか。
      バーの幅と状態(warn / over)も現物から見る。

  (6) **うちの投稿ゲート(`x_post.weighted_len`)を同じ参照に当てる**。
      道具と同じものを別に書いたコードなので、**2つとも同じ参照で測る**。

`--sabotage` でわざと傷を入れて、上の検査が本当に落ちるかを見る(空振り確認)。

    python lab/scripts/test_char_counter.py [--n 300] [--sabotage] [--docs <docs>]
    python lab/scripts/test_char_counter.py --page docs/en/char-counter.html
"""
import argparse
import math
import pathlib
import random
import re
import sys
import unicodedata

import regex as regexmod

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402
from skipwatch import SkipWatch  # noqa: E402

JA_CHARS = re.compile("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？　]")

# ---------------------------------------------------------------- 参照(1)
# twitter-text の設定 v3。重み 100(=1) になる符号位置の範囲。
W1_RANGES = [(0, 4351), (8192, 8205), (8208, 8223), (8242, 8247)]
URL_LEN = 23
MAX_WEIGHT = 280

# 参照(2) 書記素クラスタ(UAX #29)は第三者の regex モジュールに切ってもらう。
GRAPHEME = regexmod.compile(r"\X")
# RGI の絵文字とみなす手がかり。★ 素の © ® ☺ は絵文字ではない(重みは範囲どおり)。
EMOJI_HINT = regexmod.compile(
    r"\p{Emoji_Presentation}|\uFE0F|\u20E3|\p{Regional_Indicator}|\p{Emoji_Modifier}")


def cp_weight(cp):
    return 1 if any(a <= cp <= b for a, b in W1_RANGES) else 2


def ref_weight(text):
    """参照(1)+(2)。X の重み付きカウント。"""
    t = URL_RE.sub("U" * URL_LEN, text)
    w = 0
    for cl in GRAPHEME.findall(t):
        if EMOJI_HINT.search(cl):
            w += 2
        else:
            w += sum(cp_weight(ord(c)) for c in cl)
    return w


# ---------------------------------------------------------------- 参照(3)
def js_whitespace():
    """ECMAScript の WhiteSpace + LineTerminator を Unicode データから組み立てる。
    仕様: TAB VT FF SP NBSP ZWNBSP と カテゴリ Zs、それに LF CR LS PS。"""
    s = {0x09, 0x0B, 0x0C, 0x20, 0xA0, 0xFEFF, 0x0A, 0x0D, 0x2028, 0x2029}
    s |= {cp for cp in range(0x10000) if unicodedata.category(chr(cp)) == "Zs"}
    return s


JS_WS = js_whitespace()

# ⚠ URL は「`http(s)://` のあと空白まで」だが、**その「空白」も ECMAScript の集合**で決まる。
#   Python の `\S+` をそのまま使うと **U+FEFF を URL の一部として食う**ので、
#   道具(`[^\s]+`)より長く取ってしまう。実際にこの食い違いを1件踏んだので、
#   非空白の文字クラスも上の集合から組み立てる。
JS_NOT_WS = "[^" + "".join(re.escape(chr(c)) for c in sorted(JS_WS)) + "]"
URL_RE = re.compile("https?://" + JS_NOT_WS + "+")

# ---------------------------------------------------------------- 参照(4)
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")
JP_RE = re.compile("[　-ヿ一-鿿＀-￯]")


def js_strip(s):
    """JS の `String.prototype.trim`。⚠ Python の `strip()` とは集合が違う
    (NBSP はどちらも落ちるが、U+FEFF は JS だけ・U+0085 は Python だけ)。"""
    i, j = 0, len(s)
    while i < j and ord(s[i]) in JS_WS:
        i += 1
    while j > i and ord(s[j - 1]) in JS_WS:
        j -= 1
    return s[i:j]


def ref_counts(text):
    chars = list(text)
    nows = [c for c in text if ord(c) not in JS_WS]
    lines = 0 if text == "" else text.count("\n") + 1
    paras = 0 if js_strip(text) == "" else \
        len([p for p in re.split(r"\n{2,}", text) if js_strip(p)])
    words = len(WORD_RE.findall(URL_RE.sub(" ", text)))
    jp = len(JP_RE.findall(text))
    return {"all": len(chars), "nows": len(nows), "lines": lines,
            "paras": paras, "words": words, "jp": jp}


def ref_minutes_label(text, lang):
    c = ref_counts(text)
    minutes = c["jp"] / 500 + c["words"] / 200
    if minutes < 0.1 and c["all"] == 0:
        return "0分" if lang == "ja" else "0 min"
    if minutes < 1:
        return "1分未満" if lang == "ja" else "under 1 min"
    n = math.floor(minutes + 0.5)          # JS の Math.round(半分は上へ)
    return ("%d分" % n) if lang == "ja" else ("%d min" % n)


def ref_sheets(text, lang):
    """原稿用紙(日本語版・空白を除いた文字数 ÷ 400)/ ページ(英語版・単語数 ÷ 250)。"""
    c = ref_counts(text)
    if lang == "ja":
        return "%d枚" % (math.ceil(c["nows"] / 400) if c["nows"] else 0)
    return str(math.ceil(c["words"] / 250) if c["words"] else 0)


# ---------------------------------------------------------------- 見本を作る
ALPHABET = [
    "a", "b", "z", "A", "Q", "0", "7", " ", "\n", "\t", ".", ",", "'", "-", "/",
    "あ", "漢", "字", "ー", "、", "。", "ｱ", "ﾞ", "Ａ", "　",          # 日本語まわり
    "é", "é", "ñ", "ü",                                        # 合成・分解
    "ế", "ộ", "ự",                                                    # ベトナム語(U+1E00 台)
    "…", "‥", "—", "–", "‘", "’", "“", "”", "′", "″",                # 約物
    "€", "£", "¥", "©", "®", "→", "±", "∑", "★", "☺",                # 記号
    "​", "‎", " ", " ", "﻿",                # 見えない文字
    "Ω", "д", "א", "ب", "ก", "ក", "ሀ", "Ꭰ", "ᚠ", "ᐃ",               # いろいろな文字体系
    "😀", "❤️", "👍🏽", "👨‍👩‍👧", "🇯🇵", "1️⃣", "🏳️‍🌈", "𠮟", "🀄",
    "https://example.com/a/b?c=1", "http://a.co", "https://日本語.example/パス",
]

FIXED = [
    "", " ", "\n", "\n\n", "あ", "a",
    "こんにちは、世界。",
    "Hello, world! It's a test — don't panic.",
    "段落1です。\n\n段落2です。\n\n\n段落3です。",
    "https://example.com/very/long/path/that/is/definitely/longer/than/23",
    "URLが2つ https://a.example/1 と https://b.example/2 あります",
    "😀😀😀",
    "👨‍👩‍👧👨‍👩‍👧",
    "🇯🇵🇺🇸",
    "❤️❤️",
    "1️⃣2️⃣3️⃣",
    "👍🏽👍🏻",
    "©®☺",
    "…" * 10,
    "€100 → £80 ± 2",
    "Tiếng Việt có dấu",
    "ሀሁሂሃ",                       # エチオピア文字(4351 より上・全角ではない)
    "‎‏​",         # 書字方向・ゼロ幅
    "a" * 279 + "b",
    "あ" * 141,
    "  \t   ﻿  ",
    "行1\n行2\n行3",
    "末尾に改行\n",
    # ★読了時間の丸めは「1分を超えていて、なお端数が半分以上」でないと現れない。
    #   ランダムな見本はほぼ全部「1分未満」に落ちるので、手で置いておく
    #   (`--sabotage` の time が最初これで素通りした。「薄い領域」9例目)。
    "あ" * 800,                    # 1.6分 → 四捨五入 2 / 切り捨て 1
    "あ" * 750,                    # ちょうど 1.5分(JS の Math.round は上へ)
    "word " * 300,                 # 300語 = 1.5分
    "あ" * 1200 + "\n\n" + "word " * 100,
]


def build_cases(n, rnd):
    cases = list(FIXED)
    while len(cases) < n:
        k = rnd.randint(1, 40)
        cases.append("".join(rnd.choice(ALPHABET) for _ in range(k)))
    return cases[:n]


def build_codepoints(rnd):
    """参照(1)の範囲の境目を必ず含む符号位置の一覧(1文字ずつ重みを見る)。"""
    cps = set()
    for a, b in W1_RANGES:
        for x in (a - 1, a, a + 1, b - 1, b, b + 1):
            if 0 <= x <= 0x10FFFF:
                cps.add(x)
    cps |= {0x2026, 0x20AC, 0x00A9, 0x00AE, 0x1EBF, 0x1F00, 0x1200, 0x2192,
            0x3000, 0x4E00, 0xFF21, 0xFF66, 0x1F600, 0x20000}
    for _ in range(1200):
        cps.add(rnd.randint(0, 0x10FFFF))
    ok = []
    for cp in sorted(cps):
        ch = chr(cp)
        if 0xD800 <= cp <= 0xDFFF:                 # 単独のサロゲートは文字にならない
            continue
        if unicodedata.category(ch) in ("Cs",):
            continue
        ok.append(cp)
    return ok


# ---------------------------------------------------------------- 画面を読む
VIA_UI = """(o) => {
  const el = document.getElementById('src');
  el.value = o.text;
  el.dispatchEvent(new Event('input'));
  const g = id => { const e = document.getElementById(id); return e ? e.textContent : null; };
  const bar = document.getElementById('x-bar');
  const over = document.getElementById('x-jp') || document.getElementById('x-over');
  return {all:g('c-all'), nows:g('c-nows'), lines:g('c-lines'), paras:g('c-paras'),
          words:g('c-words'), genko:g('c-genko'), pages:g('c-pages'),
          x:g('c-x'), time:g('c-time'),
          barClass: bar.className, barWidth: bar.firstElementChild.style.width,
          over: over ? over.textContent : null};
}"""

CALL_WEIGHT = "(a) => a.map(t => xWeight(t))"
CALL_CP = "(a) => a.map(cp => xWeight(String.fromCodePoint(cp)))"


def unformat(s):
    """参照(5)。桁区切りをほどいて数に戻す。"""
    if s is None:
        return None
    t = s.replace(",", "").replace(" ", "").strip()
    return int(t) if re.fullmatch(r"-?\d+", t) else None


def check_all(page, cases, cps, lang, label):
    fails = []
    n = dict(counts=0, weight=0, display=0, bar=0, cp=0, sheets=0, time=0)

    # --- 1件ずつ画面から読む ---
    for i, text in enumerate(cases):
        got = page.evaluate(VIA_UI, {"text": text})
        want = ref_counts(text)
        w = ref_weight(text)

        # 参照(5) 表示の可逆(桁区切りをほどく)
        nums = {k: unformat(got[k]) for k in ("all", "nows", "lines", "paras", "words", "x")}
        if any(v is None for v in nums.values()):
            fails.append("#%d 画面の数が読み戻せない: %r" % (i, got))
            continue
        n["display"] += 1

        # 参照(4) 数え上げ
        bad = [k for k in ("all", "nows", "lines", "paras", "words") if nums[k] != want[k]]
        if bad:
            fails.append("#%d %s が違う(道具 %s / 参照 %s): %r"
                         % (i, "・".join(bad), {k: nums[k] for k in bad},
                            {k: want[k] for k in bad}, text[:40]))
            continue
        n["counts"] += 1

        # 参照(1)(2) X の重み付き
        if nums["x"] != w:
            fails.append("#%d Xの重みが違う(道具 %d / 参照 %d): %r"
                         % (i, nums["x"], w, text[:40]))
            continue
        n["weight"] += 1

        # 参照(5) バーの幅と状態
        want_pct = min(100.0, w / MAX_WEIGHT * 100)
        want_cls = "bar" + (" over" if w > MAX_WEIGHT else
                            " warn" if w > MAX_WEIGHT * 0.9 else "")
        # ⚠ CSS の幅は書き出すときに丸められる(6.428571… → "6.42857%")ので、
        #   完全一致ではなく丸めの分だけ許す。状態(warn / over)は完全一致で見る。
        got_pct = float(got["barWidth"].rstrip("%")) if got["barWidth"] else 0.0
        if abs(got_pct - want_pct) > 1e-4 or got["barClass"] != want_cls:
            fails.append("#%d バーが違う(幅 %s/%s・状態 %r/%r)"
                         % (i, got_pct, want_pct, got["barClass"], want_cls))
            continue
        n["bar"] += 1

        # 参照(4) 原稿用紙 / ページ・読了時間
        sheets = got["genko"] if lang == "ja" else got["pages"]
        if sheets != ref_sheets(text, lang):
            fails.append("#%d 原稿用紙/ページが違う(道具 %r / 参照 %r): %r"
                         % (i, sheets, ref_sheets(text, lang), text[:40]))
            continue
        n["sheets"] += 1
        if got["time"] != ref_minutes_label(text, lang):
            fails.append("#%d 読了時間が違う(道具 %r / 参照 %r): %r"
                         % (i, got["time"], ref_minutes_label(text, lang), text[:40]))
            continue
        n["time"] += 1

    # --- 符号位置を1つずつ(範囲の境目を必ず含む) ---
    got = page.evaluate(CALL_CP, cps)
    diffs = []
    for cp, g in zip(cps, got):
        w = ref_weight(chr(cp))
        if g == w:
            n["cp"] += 1
        else:
            diffs.append((cp, g, w))
    if diffs:
        fails.append("符号位置の重みが %d 件違う(先頭5件: %s)"
                     % (len(diffs), ", ".join("U+%04X 道具%d/参照%d" % d for d in diffs[:5])))

    # --- 英語版に日本語が出ていないか ---
    if lang == "en":
        got = page.evaluate(VIA_UI, {"text": "Hello 世界 https://a.co 😀"})
        left = JA_CHARS.findall("".join(v for v in got.values() if isinstance(v, str)))
        if left:
            fails.append("英語版の画面に日本語が %d 文字: %s" % (len(left), left[:8]))
    return n, fails


# ---------------------------------------------------------------- 空振り確認
SABOTAGE = {
    # 1. 重み1の範囲の上端を広げる(ベトナム語・エチオピア文字などが1になる)
    "range": lambda s: s.replace("[[0, 4351],", "[[0, 8000],"),
    # 2. 絵文字を1つ2ではなく符号位置ごとに数える
    "emoji": lambda s: s.replace("if (EMOJI_RE.test(cl))", "if (false)"),
    # 3. URL を実際の長さで数える
    "url": lambda s: s.replace('"U".repeat(23)', '"U"'),
    # 4. 空白を除く数え方を Python 風(U+FEFF を空白としない)にする
    "space": lambda s: s.replace('t.replace(/\\s/g, "")', 't.replace(/[ \\t\\n\\r]/g, "")'),
    # 5. 行数を「改行の数」にする(最後の行を落とす)
    "lines": lambda s: s.replace('t.split("\\n").length', 't.split("\\n").length - 1'),
    # 6. 段落の空行の判定を1行以上にする
    "paras": lambda s: s.replace("/\\n{2,}/", "/\\n{1,}/"),
    # 7. 原稿用紙・ページを切り捨てにする
    "sheets": lambda s: s.replace("Math.ceil(noWs.length / 400)", "Math.floor(noWs.length / 400)")
                         .replace("Math.ceil(words / 250)", "Math.floor(words / 250)"),
    # 8. 読了時間の丸めを切り捨てにする
    "time": lambda s: s.replace("Math.round(minutes)", "Math.floor(minutes)"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=str(pathlib.Path.home() / "hirulab-tools" / "docs"))
    ap.add_argument("--page", help="この HTML を見る(既定は日本語版と英語版の両方)")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--sabotage", action="store_true")
    ap.add_argument("--update-skip-baseline", action="store_true",
                    help="skipwatch の基準を更新する(母数の作り方を変えたとき)")
    args = ap.parse_args()

    docs = pathlib.Path(args.docs)
    if args.page:
        p = pathlib.Path(args.page)
        pages = [(p, "en" if "en" in p.parts or p.name.startswith("en") else "ja",
                  "指定されたページ")]
    else:
        pages = [(docs / "char-counter" / "index.html", "ja", "日本語版"),
                 (docs / "en" / "char-counter.html", "en", "英語版")]
    for p, _, _ in pages:
        if not p.exists():
            sys.exit("ページが見つかりません: %s" % p)

    rnd = random.Random(args.seed)
    cases = build_cases(args.n, rnd)
    cps = build_codepoints(random.Random(args.seed))

    import tempfile
    tmp = tempfile.TemporaryDirectory()
    work = pathlib.Path(tmp.name)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        if args.sabotage:
            src = pages[0][0].read_text(encoding="utf-8")
            small = build_cases(60, random.Random(args.seed))
            small_cps = cps[:200]
            print("--- わざと壊して、検査が落ちるかを見る ---")
            for name, fn in SABOTAGE.items():
                broken = fn(src)
                if broken == src:
                    browser.close()
                    sys.exit("仕込みが当たっていない(元のコードが変わっていない): %s" % name)
                f = work / ("broken-%s.html" % name)
                f.write_text(broken, encoding="utf-8", newline="\n")
                page.goto(f.as_uri())
                _, fails = check_all(page, small, small_cps, "ja", "日本語版")
                print("  %-8s → %s" % (name, "検出した(%d件)" % len(fails)
                                       if fails else "★素通りした"))
                if not fails:
                    browser.close()
                    sys.exit("空振り: %s を仕込んでも検査が落ちない" % name)
            browser.close()
            print("\n%d 種すべて検出した。" % len(SABOTAGE))
            return 0

        result, fails = {}, []
        for path, lang, label in pages:
            page.goto(path.resolve().as_uri())
            got, f = check_all(page, cases, cps, lang, label)
            result[label] = got
            fails += ["%s %s" % (label, x) for x in f]
        browser.close()

    print("見本 %d 通り × %d 版 / 符号位置 %d 個" % (len(cases), len(pages), len(cps)))
    for label, g in result.items():
        print("  %s: 数え上げ %d / Xの重み %d / 表示の可逆 %d / バー %d / "
              "原稿用紙 %d / 読了時間 %d / 符号位置 %d"
              % (label, g["counts"], g["weight"], g["display"], g["bar"],
                 g["sheets"], g["time"], g["cp"]))

    # --- 参照(6) うちの投稿ゲートも同じ参照に当てる ---
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from x_post import weighted_len            # noqa: E402
    gate_bad = [t for t in cases if weighted_len(t) != ref_weight(t)]
    print("\n投稿ゲート(x_post.weighted_len)を同じ参照に当てる: "
          "一致 %d / %d" % (len(cases) - len(gate_bad), len(cases)))
    if gate_bad:
        low = [t for t in gate_bad if weighted_len(t) < ref_weight(t)]
        print("  食い違い %d 件(うち**少なく数えている**= 危ない側 %d 件)"
              % (len(gate_bad), len(low)))
        for t in gate_bad[:3]:
            print("    ゲート %d / 参照 %d: %r" % (weighted_len(t), ref_weight(t), t[:40]))

    sw = SkipWatch("test_char_counter")
    sw.check("[1] 画面の検査を最後まで通らなかった見本",
             len(cases) - result[pages[0][2]]["time"], len(cases))
    skip_code = sw.report()

    if fails:
        print("\n★食い違い %d 件" % len(fails))
        for f in fails[:20]:
            print("  " + f)
        return 1
    print("\n食い違い 0")
    return skip_code


if __name__ == "__main__":
    sys.exit(main())
