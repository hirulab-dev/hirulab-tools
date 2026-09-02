#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「もう一方の言語の版へ行く行」を、どのページでも同じ形・同じ場所に揃える。

2026-08-28 新設。決まりは1つだけ:
**もう一方の言語への行は、「ほかの道具」ナビのいちばん最後に、1本だけ置く。**

この決まりは英語ページ側でだけ守られている前提で `add_tool_link.py` が書かれていて
(末尾の行が言語の行なら、その手前に足す)、実際には3通りの壊れ方をしていた。

1. **英語版があるのに、日本語ページからのリンクが無い**
   `docs/base64/` と `docs/qr/` が実際にそうだった。hreflang は両側に入っていたので、
   既存のどの検査にも掛からなかった(→ `check_site.py` に検査を足した)。
2. **日本語ページでは言語の行が一覧の途中に取り残されていた**
   道具が増えるたびに後ろへ積まれていたため。`add_tool_link.py` はこの行を目印にして
   手前へ入れるので、場所がずれていると新しい道具が一覧の途中に入る。
3. **1行に `<li>` が2つ乗っている行がある**
   過去に言語の行と同じ行へ足してしまった跡。英語ページ4本(char-counter / csv /
   palette / regex-tester)がそうで、画面では言語の行が最後に見えていなかった。

対応表は下の PAIRS。英語版を出したらここに1行足すこと。

    python lab/scripts/fix_lang_link.py --docs docs [--check]
"""
import argparse
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import en_pages  # noqa: E402

# ★2026-09-03: 対応表を `en_pages.py` に1本化した。
#   ここには**18件しか書いていなかった**(全25本のうち contrast / diff / image / json /
#   page-contrast / unit の6本が無い)。= この道具はその6ページを**一度も見ていなかった**。
#   現物はたまたま正しかったので、誰も気づかない形だった
#   (9/1〜9/2 に4件出た「黙って空振りする検査」と同じ型)。
PAIRS = en_pages.PAGES

JA_NAV = re.compile(r'(  <nav class="hl-nav">\n    <h2>ほかの道具</h2>\n    <ul>\n)(.*?)(\n    </ul>)', re.S)
EN_NAV = re.compile(r'(  <nav class="hl-nav">\n    <h2>Other tools</h2>\n    <ul>\n)(.*?)(\n    </ul>)', re.S)
NAV_ARRAY = re.compile(r"(var NAV_LINKS = \[\n)(.*?)(\n\];)", re.S)
LI = re.compile(r"<li>.*?</li>", re.S)

JA_MARKS = ("English version",)
# 英語ページ側の呼び名は2通りある(古いページは日本語まじり)。どちらも同じ役目の行
EN_MARKS = ("Japanese version", "日本語版")


def normalize(body, marks, fallback):
    """1行1項目にほどき、marks を含む行を最後にまとめる。無ければ fallback を足す。"""
    items = []
    for line in body.rstrip("\n").split("\n"):
        found = LI.findall(line)
        items.extend(found if found else [line.strip()])
    # ★空行は落とす(2026-09-03)。落とさないと、あとで "      " + x を付けるときに
    #   **空白だけの行**が生まれる。1行に <li> が2つ並んでいるページ(contrast・image・
    #   frima-profit)をほどくと必ずここに当たる
    items = [x for x in items if x]
    kept = [x for x in items if not any(m in x for m in marks)]
    tail = [x for x in items if any(m in x for m in marks)]
    added = not tail
    if added:
        # fallback が None のときは「並べ直すだけ」(生成スクリプトの雛形など、
        # どのページ向けかがここでは決まらない場合)
        tail = [] if fallback is None else [fallback]
        added = bool(tail)
    return "\n".join("      " + x for x in kept + tail), added


def normalize_array(body, href, label="English version"):
    """`var NAV_LINKS = [...]` のナビ。同じことを配列に対してやる。

    ★2026-09-02 夜: `label` を引数にした。それまで "English version" 固定だったため、
      **英語ページ側では呼び出しようがなく** `href_for_array=None` が渡っていた。
      その結果 `en/password.html`(ナビが JS の配列)は毎回
      **「!! ナビが見つからない」と出して黙って素通り**していた
      (実際には行はあり、たまたま正しかった)。エラーが出続けるのに結果は正しいので、
      その表示が**見ないことの言い訳**として定着していた形。
    """
    text = body.rstrip()
    items = re.findall(r'\["([^"]*)",\s*"([^"]*)"\],?', text)
    entry = (href, label)
    # もう正しい形なら1バイトも動かさない(書き方を変えると差分が全体に出るため)
    if items and items[-1] == entry:
        return body, False
    added = not any(l == label for _, l in items)
    items = [(h, l) for h, l in items if l != label] + [entry]
    return "\n".join('  ["%s", "%s"]%s' % (h, l, "," if i < len(items) - 1 else "")
                     for i, (h, l) in enumerate(items)), added


def patch(path, pattern, marks, fallback, href_for_array=None, array_label="English version"):
    text = path.read_text(encoding="utf-8")
    m = pattern.search(text)
    if m:
        body, added = normalize(m.group(2), marks, fallback)
        new = text[:m.start()] + m.group(1) + body + m.group(3) + text[m.end():]
    else:
        m = NAV_ARRAY.search(text)
        if not m or href_for_array is None:
            return "!! ナビが見つからない", text, False
        body, added = normalize_array(m.group(2), href_for_array, array_label)
        new = text[:m.start()] + m.group(1) + body + m.group(3) + text[m.end():]
    if new == text:
        return "そのまま", text, False
    return ("★リンクが無かったので追加" if added else "並びを直した"), new, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs",
                    default=str(pathlib.Path.home() / "hirulab-tools" / "docs"))
    ap.add_argument("--check", action="store_true", help="書き換えずに違いだけ出す")
    a = ap.parse_args()
    docs = pathlib.Path(a.docs)

    changed = 0
    for slug, en in sorted(PAIRS.items()):
        for path, pattern, marks, fallback, arr, arr_label in (
            (docs / slug / "index.html", JA_NAV, JA_MARKS,
             '<li><a href="../en/%s">English version</a></li>' % en, "../en/" + en,
             "English version"),
            # ★配列ナビの英語ページも面倒を見る(2026-09-02 夜)。
            #   ここが None だったせいで en/password.html は毎回「ナビが見つからない」だった。
            (docs / "en" / en, EN_NAV, EN_MARKS,
             '<li><a href="../%s/">Japanese version</a></li>' % slug, "../" + slug + "/",
             "Japanese version"),
        ):
            if not path.exists():
                print("%-22s !! ページが無い" % path)
                continue
            msg, new, did = patch(path, pattern, marks, fallback, arr, arr_label)
            name = "/".join(path.parts[-2:])
            print("%-24s %s" % (name, msg))
            if did:
                changed += 1
                if not a.check:
                    path.write_text(new, encoding="utf-8", newline="\n")
    print("\n直したページ: %d" % changed)


if __name__ == "__main__":
    main()
