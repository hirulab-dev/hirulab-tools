#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""英語版と日本語版で、**文字列の中身以外のコード**が同じかを全ページ分見る(2026-09-01 朝 新設)。

## なぜ作ったか

2026-09-01 未明に `en/csv.html` で見つけた実バグ:
**行をつなぐ区切りが日本語版では U+0001、英語版では空文字**になっていて、
英語版だけが `ab,c` と `a,bc` を「まったく同じ内容の行」と名指ししていた。
6日以上気づかなかった理由は単純で、**英語版を手で書いたページには「日本語版と同じか」を
見る仕組みが無かった**から。`make_en_*.py` で生成しているページは
「文字列の中身を空にすると日英でバイト一致」を生成のたびに検査しているので、
同じ事故が構造的に起きない。**生成器を持たないページだけが野放し**だった。

## 何を見るか

  - 文字列リテラルの中身・コメント・正規表現リテラルの中身を空にしてから比べる
    (= 訳した文言の違いは無視して、**処理だけ**を見る)
  - 生成器を持つページは「一致していること」が要求。1バイトでも違えば ★
  - 生成器を持たない**手書きの英語版**は、一致しないのが普通なので、
    **違う行の数と中身を出して人が見る**。ここに `en/csv.html` の型の傷が眠っている

    python lab/scripts/check_en_parity.py [--docs <docs>] [--page en/csv.html] [--show 20]

## ★2026-09-02 夜: **この道具は「対を持つページ」しか見ていなかった**

上の説明には「`docs/en/*.html` を全部走査して」と書いてあったが、**走査していない**。
実際に回していたのは下の `PAIRS`(手で書いた対応表)だけで、
**対応表に無いページは、あってもなくても何も言わない**形だった。

そのせいで今日、事実でないことを何度も書いた:
**「英語版を持たない道具は0本」「日本語版はあるのに英語版が無いページは0本」**
(2026-09-02 朝・昼のログと `accounts.md`)。数えたら **`take-home/`(手取り計算機)と
`frima-profit/`(フリマ利益計算機)の2本に英語版が無い**。
どの検査にも掛からなかった理由は3つとも同じ型:
  - `check_site.py` の hreflang 検査は **hreflang があるページしか見ない**
    (英語版が無いページは hreflang も無いので、そもそも土俵に上がらない)
  - `check_site.py` のナビ完全性検査は **在るものから「揃うべき集合」を作る**
    ので、英語版が減れば要求も一緒に減る
  - この道具は **手で書いた対応表**を回していた(`site_pages.py` を作った動機そのもの)

→ **日本語側・英語側の両方を `docs/` から数え、対応表の外を必ず名指しする**形にした。
   英語版を作らないと決めたページは `NO_EN` に**理由つきで**書く。
   書いていないものは ★ にする(=「知らなかった」と「決めた」を区別する)。
"""
import argparse
import difflib
from html.parser import HTMLParser
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank  # noqa: E402
from site_pages import discover  # noqa: E402
import en_pages  # noqa: E402

# ★2026-09-03: 対応表・生成器の一覧・`NO_EN` を `en_pages.py` に移した。
#   同じ対応が3か所に手書きされていて、**3つとも中身が違っていた**
#   (この表は24件、`fix_lang_link` は18件、`sync_en_nav` は14件)。
#   ここは引くだけにする。`GENERATED` は手書きの集合をやめ、
#   **生成器が実在するかで決める**(足し忘れが起こりようがない)。
PAIRS = en_pages.by_en()
GENERATED = en_pages.generated()
NO_EN = en_pages.NO_EN


def script_span(html):
    m = re.search(r"<script>\n(.*)</script>", html, re.S)
    if not m:
        return None
    core = html[m.start(1):m.end(1)]
    # ★`NAV_LINKS` は「英語版がある道具だけ」を載せるので日英で項目数が違うのが仕様。
    #   `make_en_password.py` が自分の照合から外しているのと同じ理由でここでも外す。
    return re.sub(r"var NAV_LINKS = \[.*?\];\n", "", core, flags=re.S)


def norm(src):
    """文字列・コメント・正規表現の中身を空にして、行ごとに前後の空白を落とす。"""
    b = blank(src, blank_regex=True)
    return [ln.strip() for ln in b.split("\n")]


def flat(src):
    """★改行の入れ方の違いを消した形。
    訳した文言が長くて折り返しが変わっただけ、を「処理が違う」と言わないため
    (`en/password.html` の表がこの形で、最初 15 行ちがうと出た)。"""
    return re.sub(r"\s+", " ", blank(src, blank_regex=True)).strip()


# ── ★2026-09-03 追加: HTML と CSS の日英パリティ ──────────────────────────
#
# `inspection-coverage.md` の「次に疑うべき所」1番の根治。ここまでの検査は
# **`<script>` の中しか比べていなかった**。HTML と CSS はその外なので、
# 9/2 朝に **英語版だけに `<a class="hl-back">` を足して AA 不合格を出した**とき、
# 日英パリティは何も言わなかった(拾ったのはコントラスト検査)。
#
# 何を見るか: **タグの骨組み**(タグ名 + 構造にかかわる属性)と **<style> の中身**。
#   - 文言は言語で変わるので見ない
#   - `href` / `content` も変わってよい(canonical・OGP・言語リンク)。ただし
#     **`id` / `class` / `type` / `data-*` は日英で同じでなければならない**
#     (検証がここを鍵にして画面を読むため。9/2 の `data-k` はまさにこれ)
#   - `<nav class="hl-nav">` は中身が言語ごとに違うのが仕様なので**丸ごと外す**
#     (あちらは `check_site.py` と `sync_en_nav.py` が見ている)
STRUCT_ATTRS = ("id", "class", "type", "name", "for", "checked", "disabled",
                "colspan", "rowspan", "value", "min", "max", "step")
NAV_BLOCK = re.compile(r'  <nav class="hl-nav">.*?\n  </nav>', re.S)
STYLE_BLOCK = re.compile(r"<style>(.*?)</style>", re.S)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def css_rules(css):
    """CSS からコメントを落とし、空白を畳んだ形。**規則だけ**を比べるため。"""
    return re.sub(r"\s+", " ", CSS_COMMENT.sub("", css)).strip()


# ★文中の強調は「文言の一部」なので骨組みから外す。
#   訳すと強調する語が変わるのは当たり前で(日本語の「〜は必ず」と英語の "always" は
#   同じ位置に来ない)、そこを差と呼ぶと**本物の差が埋もれる**。
#   最初に書いたときはこれを入れていて、7ページで「骨組みがちがう」と出たが、
#   中を見たら**全部 <strong>/<b>/<code>/<em> の位置**だった。
INLINE = {"b", "strong", "em", "i", "u", "small", "code", "kbd", "mark",
          "abbr", "sub", "sup", "br", "wbr", "s", "q", "cite", "var", "samp"}

# ★**わざと日英で違えてあるところ**(英語ファイル名 -> (差の数, 理由))。
#   `NO_EN` と同じ考え方で、**黙らせるのではなく「いくつ違うか」を固定する**。
#   数を書いておくと、**そのページに新しい差が出たとき数が変わって ★ になる**
#   (「このページは違ってよい」とだけ書くと、以後そのページは野放しになる)。
# ★**コードのほうの、わざと違えてあるところ**(英語ファイル名 -> (差の行数, 理由))。
#   2026-09-03 新設。上の `HTML_DIFF_OK` と同じ扱いで、数を固定する。
#   ⚠ 数は `unified_diff` の +/- を数えたものなので、1か所の書き換えは **2行**になる。
#   ⚠ 生成器のほうにも同じ差の登録(`CODE_DIFF`)があるが、**わざと別々に持っている**。
#      検査が検査される側と同じ表を読むと、その表を壊したとき両方いっしょに壊れて空振りする
#      (`regen_ogp.py` の `NO_LINE_START_CHECK` と同じ理由)。
CODE_DIFF_OK = {
    "char-counter.html": (2, "原稿用紙(400字詰め)が何枚か vs 書籍のページ(約250語)が何枚か。"
                             "単位そのものが日本語圏と英語圏で違うので、訳ではなく別の式になる"),
}

HTML_DIFF_OK = {
    "csv.html": (2, "英語版だけに段落が1つ多い。見本データが日本語なのはなぜか"
                    "(ASCIIだけのファイルでは文字コード判定に仕事が無い)の説明で、"
                    "日本語で読む人には要らない"),
    "date.html": (10, "元号の `option value` を訳している(令和→Reiwa)。"
                      "値は画面にも出る名前で、JS 側の対応表も同じ文字列で引くので日英で揃っている"),
}

# `<style>` の中身の差。★**2026-09-03 昼 新設**。
#   それまで CSS の差は「(1 個 / 1 個)」= `<style>` の**個数**しか出さず、
#   **どの規則が違うのかを一度も言わなかった**。免除の仕組みも無かった。
#   timezone が初めてここに当たったので、HTML_DIFF_OK と同じ「数を固定する」形に揃えた。
CSS_DIFF_OK = {
    "timezone.html": (2, "本文のフォント指定。日本語版は Hiragino/Noto Sans JP/Meiryo を先に置くが、"
                         "英語の読み手にはこの3つが当たらない(当たっても日本語用の字形)ので、"
                         "英語版は OS 標準の欧文フォントから並べている"),
}


class Skeleton(HTMLParser):
    """タグ名と構造にかかわる属性だけを並べる。文言・URL・文中の強調は落とす。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag in INLINE and not any(k in ("id", "class") for k, _ in attrs):
            return
        d = dict(attrs)
        keep = [(k, d[k]) for k in STRUCT_ATTRS if k in d]
        keep += [(k, v) for k, v in sorted(d.items()) if k.startswith("data-")]
        self.out.append(tag + "".join(" %s=%s" % kv for kv in sorted(keep)))

    def handle_endtag(self, tag):
        if tag in INLINE:
            return          # 開き側を落としたので閉じ側も落とす(class つきは稀なので割り切る)
        self.out.append("/" + tag)


def skeleton(html):
    p = Skeleton()
    p.feed(NAV_BLOCK.sub("", html))
    return p.out


def html_parity(docs, names, show):
    """生成ページについて HTML の骨組みと CSS を日英で比べる。(行, ★の数)。"""
    lines, bad, waived = [], 0, []
    seen = 0
    for name in names:
        if name not in GENERATED:
            continue                      # 手書きは一致しないのが普通
        ja_p, en_p = docs / PAIRS[name], docs / "en" / name
        if not (ja_p.exists() and en_p.exists()):
            continue
        ja, en = ja_p.read_text(encoding="utf-8"), en_p.read_text(encoding="utf-8")
        seen += 1

        a, b = skeleton(ja), skeleton(en)
        if a != b:
            d = [ln for ln in difflib.unified_diff(a, b, lineterm="", n=0)
                 if ln[:1] in "+-" and ln[:3] not in ("+++", "---")]
            want, why = HTML_DIFF_OK.get(name, (0, None))
            if why and len(d) == want:
                waived.append("  わざと違う: %s(%d か所)— %s" % (name, want, why))
            else:
                extra = "" if why is None else \
                    "(わざと違うのは %d か所のはず。数が変わった)" % want
                lines.append("★ %s: HTML の骨組みが %d か所ちがう%s" % (name, len(d), extra))
                lines += ["    " + ln[:140] for ln in d[:show]]
                bad += 1

        # ★CSS のコメントは文言なので落とす(JS で blank() がやっているのと同じ線引き)。
        #   最初はそのまま比べていて6ページで差が出たが、**6ページとも中身は
        #   翻訳された注釈だけ**だった。規則そのものは1バイトも違わない。
        sa, sb = [css_rules(x) for x in STYLE_BLOCK.findall(ja)], \
                 [css_rules(x) for x in STYLE_BLOCK.findall(en)]
        if sa != sb:
            # ★どの規則が違うのかを必ず出す(2026-09-03 昼)。個数だけ出していた頃は、
            #   本物の差と意図した差が同じ1行に見えていた。
            # `css_rules` は畳んだ**1本の文字列**を返すので、規則の単位(`}`)で割ってから比べる
            split = lambda blocks: [r.strip() + "}" for blk in blocks
                                    for r in blk.split("}") if r.strip()]
            fa, fb = split(sa), split(sb)
            d = [ln for ln in difflib.unified_diff(fa, fb, lineterm="", n=0)
                 if ln[:1] in "+-" and ln[:3] not in ("+++", "---")]
            want, why = CSS_DIFF_OK.get(name, (0, None))
            if why and len(d) == want and len(sa) == len(sb):
                waived.append("  わざと違う(CSS): %s(%d か所)— %s" % (name, want, why))
            else:
                extra = "" if why is None else \
                    "(わざと違うのは %d か所のはず。数が変わった)" % want
                lines.append("★ %s: <style> の中身が %d か所ちがう(ブロック %d 個 / %d 個)%s"
                             % (name, len(d), len(sa), len(sb), extra))
                lines += ["    " + ln[:140] for ln in d[:show]]
                bad += 1

    lines += waived
    lines.append("わざと違う扱い: %d ページ(数を固定してあるので、増えれば ★ になる)"
                 % len(waived))
    lines.append("見た範囲: 生成ページ %d 組の**タグの骨組み**"
                 "(タグ名 + %s + data-*)と **<style> の中身**"
                 % (seen, "/".join(STRUCT_ATTRS[:4])))
    lines.append("見ていない範囲: 文言 / href・content(URL は日英で違ってよい)/ "
                 "`<nav class=\"hl-nav\">`(言語ごとに中身が違うのが仕様。"
                 "check_site.py と sync_en_nav.py が見ている)/ 手書きの%dページ / "
                 % (len(names) - seen) +
                 "**JS が組み立てる HTML**(take-home の `data-k` はテンプレート文字列の中なので"
                 "ここには映らない。あちらは <script> のバイト一致が見ている)")
    return lines, bad


def coverage(docs):
    """`docs/` を数えて、**対応表の外**を名指しする(2026-09-02 夜 新設)。

    返り値 (見出し行のリスト, ★の件数)。
    ★になるのは3種類:
      - 英語ページがあるのに `PAIRS` に無い    … この道具が一度も見ていないページ
      - `PAIRS` が指す日本語ページが実在しない  … 対応表が古い
      - 英語版が無いのに `NO_EN` にも無い       … 見落とし
    `NO_EN` に書いてあるページは ★ にしないが、**本数と名前は必ず出す**。
    """
    keys = discover(docs)
    ja = {k for k in keys if k.endswith("/") and k != "" and not k.startswith("en/")}
    en = {k for k in keys if k.startswith("en/") and not k.endswith("/")}
    paired_ja = {v[: -len("index.html")] for v in PAIRS.values()}
    paired_en = {"en/" + n for n in PAIRS}

    lines, bad = [], 0
    for k in sorted(en - paired_en):
        lines.append("★ 対応表(PAIRS)に無い英語ページ: %s(この道具は一度も見ていない)" % k)
        bad += 1
    for k in sorted(paired_ja - ja):
        lines.append("★ 対応表が指す日本語ページが実在しない: %s" % k)
        bad += 1
    missing = sorted(ja - paired_ja)
    for k in missing:
        if k in NO_EN:
            lines.append("  英語版なし(把握ずみ): %s — %s" % (k, NO_EN[k]))
        else:
            lines.append("★ 英語版が無いのに `NO_EN` にも書いていない: %s" % k)
            bad += 1
    for k in sorted(set(NO_EN) - set(missing)):
        lines.append("★ `NO_EN` の記述が古い(英語版はある/ページが無い): %s" % k)
        bad += 1

    lines.append("見た範囲: 日本語の道具ページ %d 本 / 英語ページ %d 本 / 対応表 %d 組"
                 " / 英語版なし %d 本(%s) / `NO_EN` の記載 %d 本"
                 % (len(ja), len(en), len(PAIRS), len(missing),
                    " ".join(missing) if missing else "無し", len(NO_EN)))
    lines.append("見ていない範囲: 画面の文言そのもの / 一覧ページ(トップ・en/)"
                 "(HTML と CSS は 2026-09-03 から上の節で見ている)")
    return lines, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=str(pathlib.Path.home() / "hirulab-tools" / "docs"))
    ap.add_argument("--page", help="この英語ページだけ見る(例 csv.html)")
    ap.add_argument("--show", type=int, default=6, help="手書きページで出す差分の行数")
    args = ap.parse_args()

    docs = pathlib.Path(args.docs)
    names = [args.page.split("/")[-1]] if args.page else sorted(PAIRS)
    bad, rows = [], []

    for name in names:
        ja_rel = PAIRS.get(name)
        if ja_rel is None:
            print("対応表に無い英語ページ: %s(PAIRS に足すこと)" % name)
            bad.append(name)
            continue
        en_p, ja_p = docs / "en" / name, docs / ja_rel
        if not en_p.exists() or not ja_p.exists():
            print("ページが無い: %s / %s" % (en_p, ja_p))
            bad.append(name)
            continue
        en_s, ja_s = script_span(en_p.read_text(encoding="utf-8")), \
            script_span(ja_p.read_text(encoding="utf-8"))
        if en_s is None or ja_s is None:
            rows.append((name, "—", "本体のスクリプトが見つからない"))
            continue
        a, b = norm(ja_s), norm(en_s)
        diff = [ln for ln in difflib.unified_diff(a, b, lineterm="", n=0)
                if ln[:1] in "+-" and ln[:3] not in ("+++", "---")]
        gen = name in GENERATED
        if flat(ja_s) == flat(en_s):
            rows.append((name, "生成" if gen else "手書き",
                         "一致" if not diff else "一致(折り返しだけ違う)"))
        elif gen and name in CODE_DIFF_OK and len(diff) == CODE_DIFF_OK[name][0]:
            rows.append((name, "生成", "わざと %d 行ちがう — %s"
                         % CODE_DIFF_OK[name]))
        elif gen:
            extra = ""
            if name in CODE_DIFF_OK:
                extra = "(わざと違うのは %d 行のはず)" % CODE_DIFF_OK[name][0]
            rows.append((name, "生成", "★%d 行ちがう(生成器を回し直すこと)%s" % (len(diff), extra)))
            bad.append(name)
            for ln in diff[:args.show]:
                print("  %s %s" % (name, ln[:160]))
        else:
            rows.append((name, "手書き", "%d 行ちがう(手書きなので普通。中身を見ること)" % len(diff)))
            for ln in diff[:args.show]:
                print("  %s %s" % (name, ln[:160]))

    print("\n| 英語ページ | 作り | コード(文字列以外)の一致 |")
    print("|---|---|---|")
    for name, kind, state in rows:
        print("| %s | %s | %s |" % (name, kind, state))
    hand = [r for r in rows if r[1] == "手書き"]
    print("\n生成 %d ページ / 手書き %d ページ(%s)"
          % (len(rows) - len(hand), len(hand), " ".join(r[0] for r in hand)))

    # ★2026-09-03 追加: HTML と CSS(それまで、この検査の外だった)
    h_lines, h_bad = html_parity(docs, names, args.show)
    print("\n--- HTML と CSS の日英パリティ ---")
    for ln in h_lines:
        print(ln)

    # ★ページ単位で見たあと、**対応表そのもの**を docs/ と突き合わせる。
    #   --page で1ページだけ見たときも必ず回す(範囲の話はページと独立なので)。
    cov_lines, cov_bad = coverage(docs)
    print("\n--- 対応表の網羅 ---")
    for ln in cov_lines:
        print(ln)
    return 1 if (bad or cov_bad or h_bad) else 0


if __name__ == "__main__":
    sys.exit(main())
