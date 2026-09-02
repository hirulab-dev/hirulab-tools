#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日本語ページと英語ページの対応を書いた**唯一の表**(2026-09-03 未明 新設)。

## なぜ作ったか

同じ対応が**3か所に手書き**されていた。`en_common.py`(9/2 昼)のときと同じで、
「同じもののコピーが3つある」だと思って開けたら、**3つとも中身が違った**。

| 表 | 形 | 件数 | 中身 |
|---|---|---:|---|
| `check_en_parity.PAIRS` | 英語ファイル名 → 日本語ページ | 24 | 全ページ |
| `fix_lang_link.PAIRS` | 日本語スラッグ → 英語ファイル名 | 18 | **6本足りない** |
| `sync_en_nav` の3表 | 生成器 → 同期のしかた | 14 | **9本足りない** |

★**差を先に数えた**(`en_common.py` のときと同じ手順):
  - 1 と 2 は**同じ関係**で、食い違いは0件。ただし 2 には
    **contrast / diff / image / json / page-contrast / unit の6本が無い**。
    = 言語リンクを直す道具が、その6ページを**一度も見ていなかった**。
    (現物はたまたま正しかった。だから誰も気づかない形)
  - 3 は生成器23本のうち14本しか名前が無く、**9本がどの表にも無かった**。
    調べたら9本とも `en_nav.build`(実ページからナビを組み直す)を使っていて
    **同期が要らないのは本当**だった。つまり**結果は正しいが、確かめてはいなかった**
    (9/2 夜の「決めた と 見ていない は、あとから見分けがつかない」と同じ形)。
    しかも `NO_SYNC` という「同期が要らない生成器」の表は**4本ぶんだけ書かれていて、
    コードからは一度も読まれていなかった**(定義だけあって使われていない)。

## ここでの決め方

- **対応は1つの表(`PAGES`)だけ**にする。ほかの道具はここから引く。
- **生成器の名前は英語ファイル名から決まる**(`regex-tester.html` → `make_en_regex_tester.py`)。
  日本語スラッグからではない(`regex` / `tz` が英語名と違うため)。
- **「同期のしかた」は表に書かず、生成器のソースから読む**(`nav_mode`)。
  表に書くと、新しい生成器を足したときに書き忘れる = いま起きていたことがまた起きる。
"""
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent

# 日本語ページのスラッグ → 英語ページのファイル名。**ここだけが対応表**
PAGES = {
    "base64": "base64.html",
    "char-counter": "char-counter.html",
    "contrast": "contrast.html",
    "cron": "cron.html",
    "csv": "csv.html",
    "date": "date.html",
    "diff": "diff.html",
    "frima-profit": "frima-profit.html",
    "headers": "headers.html",
    "image": "image.html",
    "json": "json.html",
    "jwt": "jwt.html",
    "page-contrast": "page-contrast.html",
    "palette": "palette.html",
    "password": "password.html",
    "pattern": "pattern.html",
    "qr": "qr.html",
    "railroad": "railroad.html",
    "regex": "regex-tester.html",
    "regex-why": "regex-why.html",
    "replace": "replace.html",
    "take-home": "take-home.html",
    "tz": "timezone.html",
    "unit": "unit.html",
    "url": "url.html",
}

# 英語版が**無い**日本語ページ。値は「なぜ無いか」の状態。
# ⚠ 空にしておわりにしない。**空であること自体を毎回出す**(9/2 夜、
#   「英語版の無い道具はゼロ」と2回書いて2回とも事実でなかったため)。
NO_EN = {}


def generator_name(en_name):
    """英語ページのファイル名 → 生成器のファイル名。`None` は手書きページ。"""
    return "make_en_" + en_name[:-len(".html")].replace("-", "_") + ".py"


def generated(scripts_dir=HERE):
    """生成器を持つ英語ページの集合。**手で書いた一覧を持たない**(実在で決める)。"""
    return {en for en in PAGES.values()
            if (pathlib.Path(scripts_dir) / generator_name(en)).exists()}


def by_en():
    """英語ファイル名 → 日本語ページ(docs からの相対)。"""
    return {en: "%s/index.html" % slug for slug, en in PAGES.items()}


def slug_of(en_name):
    return next((s for s, e in PAGES.items() if e == en_name), None)


# ── 生成器がナビをどう持っているか(表に書かず、ソースから読む) ──────────────

_JA_NAV = re.compile(r'<nav class="hl-nav">\s*<h2>ほかの道具</h2>')
_EN_NAV = re.compile(r'<nav class="hl-nav">\s*<h2>Other tools</h2>')
_ARRAY = re.compile(r"var NAV_LINKS = \[")
_LIVE = re.compile(r"en_nav\.build|_en_nav\.build")

# 同期のしかた。**上から順に見て、最初に当たったものを採る**(今までの挙動と同じ順序)
ARRAY, JA_STATIC, EN_STATIC, LIVE, UNKNOWN = "配列", "日本語ナビ静的", "英語ナビ静的", "実ページから組む", "不明"


def nav_mode(script_path):
    """生成器のソースを読んで、ナビの同期がどれだけ要るかを返す。

    - `配列`           … `var NAV_LINKS = [...]` を持つ。実ページの配列で丸ごと差し替える
    - `日本語ナビ静的`   … 日本語ナビを差し替え元として持つ。実ページから同期する
    - `英語ナビ静的`     … 英語ナビだけ静的。新しい行を足す面倒だけ見る
    - `実ページから組む` … `en_nav.build` を使うので**差し替え元が無い=ずれようがない**
    - `不明`           … どれでもない。**黙って飛ばさず、名前を出して止める**
    """
    src = pathlib.Path(script_path).read_text(encoding="utf-8")
    if _ARRAY.search(src):
        return ARRAY
    if _JA_NAV.search(src):
        return JA_STATIC
    if _LIVE.search(src):
        return LIVE
    if _EN_NAV.search(src):
        return EN_STATIC
    return UNKNOWN


def all_generators(scripts_dir=HERE):
    """`make_en_*.py` を全部並べ、(生成器名, 英語ファイル名 or None, 同期のしかた) を返す。

    ★**表を回すのではなく、実在する生成器を全部回す**のがここの要。
      表を回すと、表に足し忘れた生成器が黙って落ちる(それがいま起きていた)。
    """
    d = pathlib.Path(scripts_dir)
    known = {generator_name(en): en for en in PAGES.values()}
    out = []
    for p in sorted(d.glob("make_en_*.py")):
        out.append((p.name, known.get(p.name), nav_mode(p)))
    return out
