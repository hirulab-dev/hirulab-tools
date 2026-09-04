#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公開リポジトリ側の `tools/` を、手元の `lab/scripts/` の現物と揃える(2026-09-02 朝 新設)。

## なぜ要るか

公開リポジトリには「英語版はこのスクリプトが日本語版から生成しています」と書いて
`tools/make_en_*.py` を置いてある。**ところがそれは手で写した複製で、写し忘れると黙って古くなる。**

この日に実測したら、**12本が古く、2本は存在しなかった**:

  - `make_en_url.py` ほか10本 … 差し替え元のナビが**実ページより2世代ぶん古い**
    (道具が増えるたびに `sync_en_nav.py` が手元だけを直していたため)
  - `make_en_regex_tester.py`(9/2未明に新設)と `make_en_pattern.py`(この枠で新設)は**そもそも無い**

読む人から見ると「公開してある生成器で生成すると、公開してあるページと違うものが出る」。
うちの主張は**再現できること**が中身なので、ここがずれるのは看板の傷になる。

## 決まり

- **手元(`lab/scripts/`)が原本**。`tools/` は常にその複製で、手で直さない
- 複製する対象は下の `MIRROR`(生成器・その helper・検査のうち、公開する意味のあるもの)
- `lab/assets/` の3本(`make_ogp.py` / `regen_ogp.py` / `check_ogp_overlap.py`)も同じ扱い
  (2026-09-03 夜に追加。それまで誰も両者を比べていなかった)
- それ以外で `tools/` にしか無いものは触らない
- `tools/tests/` も**手元が原本**(2026-09-04 朝に揃えた)。ただし写しは自動でしない
  =**既定のパスの決め方だけは置き場所の都合でわざと違う**本があるため。
  違いは `TESTS_DIFF_OK` に**差の行数で**固定し、増減したら ★ を出す
  (9/3 の `HTML_DIFF_OK` / `CODE_DIFF` と同じ考え方)。
  ⚠ **2026-09-04 朝の経緯**: 前夜に「28本中12本が古い」と数えて数だけ固定した状態から、
  1本ずつ差を読んで **本当に古い8本を写し・意図的な差5本を記録**に分けた。
  そのとき **公開側の2本が import で1行も動いていなかった**ことも出た
  (`test_char_counter` → ラボ側にしか無い `x_post` / `test_jsblank` → 1つ上の `jsblank`)。
  → 検査に **(2) import の連れ**と **(3) 手元にあって公開側に無い本**を足した。
  ⚠ **写す前にこの2つを見ること**。写すだけだと「動かない検証」を増やす。

    python lab/scripts/sync_tools_mirror.py            # 揃える
    python lab/scripts/sync_tools_mirror.py --check    # 見るだけ(ずれていたら終了コード1)
"""
import argparse
import os
import pathlib
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_REPO = pathlib.Path(os.path.expanduser("~/hirulab-tools"))

# 手元が原本で、公開側にも置くもの。
#   - make_en_*.py … 英語版の生成器(glob で拾うので、新設しても足し忘れが起きない)
#   - 下の HELPERS … 生成器が import するもの・生成の手順そのものを見せるもの
HELPERS = [
    "jsblank.py",         # 文字列の中身を空にする(日英のバイト一致を測る心臓部)
    "en_nav.py",          # 英語ナビを毎回ほどいて組み直す
    "en_common.py",       # 生成器21本が共通で使う道具(2026-09-02に1本化)。
                          # ★これを写し忘れると、公開してある生成器が import で落ちる
    "en_pages.py",        # 日英の対応表(2026-09-03に1本化)。同上で、写し忘れると import で落ちる
    "add_tool_link.py",   # 実ページ全部のナビに1行足す
    "sync_en_nav.py",     # 生成元を実ページから同期する
    "fix_lang_link.py",   # もう一方の言語への行を1本だけ最後に置く
    "check_en_parity.py",  # 日英の食い違いを見張る
    # ★2026-09-03: `check_en_parity.py` が import しているのに写されていなかった。
    #   公開側は 9/2 朝に置いた日から **ImportError で1度も動かない**状態だった
    #   (生成器は実際に回して確かめたが、検査のほうは回していなかった)。
    #   下の「import の連れ」検査が、書いた初回にこれを名指しした
    "site_pages.py",      # docs/ を走査して検査の対象を決める
    "check_ogp_text.py",  # OGP画像の中の文字が、ページの文言と合っているか(2026-09-03 新設)
    "publish_en_page.py",  # 英語版を1本出すときの正しい順番
    "sync_tools_mirror.py",  # これ自身。README がこの道具を名指すので、現物も置いておく
]


# ★2026-09-03 夜 追加: `lab/assets/` にも公開側と同じ道具が3本あるのに、
#   **この道具は `lab/scripts/` しか見ていなかった**ので、誰も両者を比べていなかった。
#   実際 `lab/assets/regen_ogp.py` は公開側とバイト単位で同一なのに
#   **置き場所のせいで起動即エラー**という状態が9/3昼まで残っていた(同日中に是正)。
#   ここも「手元が原本・公開側はミラー」で揃える。
ASSETS_DIR = HERE.parent / "assets"
ASSETS = ["make_ogp.py", "regen_ogp.py", "check_ogp_overlap.py"]


# ★2026-09-04 朝: 前夜の「28本中12本が古い」を1本ずつ読んで分けた結果。
#   **8本は本当に写し忘れ**(この枠で写した)。**5本は意図的な差**で、中身は
#   どれも「**既定でどのページを見るか**」だけ。手元は公開リポジトリの外にあるので
#   `docs/` を相対で指せず、公開側は逆に絶対パスを書けない、という置き場所の都合。
#   ⚠ 意図的だからといって「対象外」にはしない(それをやったのが前夜の穴)。
#     **差の行数を固定**して、そこ以外が動いたら ★ が出るようにする。
#     数は `diff` の行数(公開側にしか無い行 + 手元にしか無い行の合計、改行の差は除く)。
TESTS_DIR_NAME = "tests"
TESTS_DIFF_OK = {
    "make_qr_reference.py": (4, "使い方の例に書いたパスだけ(tools/tests/ と lab/scripts/)"),
    "test_cron.py": (2, "使い方の例に書いたパスだけ"),
    "test_frima_profit.py": (2, "既定のページ(公開側はリポジトリ相対 / 手元は ~/hirulab-tools)"),
    "test_image.py": (3, "既定のページ(同上)+ その理由のコメント1行"),
    "test_pattern.py": (3, "既定のページ(公開側は本番 / 手元は outputs/tools-dev の作業中の版)"),
    "test_qr.py": (21, "既定のページ(手元はミラーに落ちたとき名乗る節を持つ)"),
}
# 公開側にあって手元に同じ名前が無いもの(名前が違うだけで中身は対応している)
TESTS_RENAMED_OK = {"test_pattern.py": "test_pattern_tool.py"}
# 手元にあって公開side に**わざと出していない**もの。理由を必ず書く
# (2026-09-04 新設。ここに書かずに出していないと「決めた」と「見ていない」が見分けられない)
TESTS_NOT_PUBLISHED = {
    "test_qr_decode.py": "OpenCV(cv2)が要る。読み戻しの実測は README に数字で載せてあるが、"
                         "動かすのに重い依存が増えるので公開側には出していない",
    "test_seamless.py": "和柄の下ごしらえ用。25本目の検証は test_pattern.py が正本",
}


def _norm(path):
    """改行だけの差は「古い」と数えない(公開側は CRLF で入っているものがある)。"""
    return path.read_bytes().replace(b"\r\n", b"\n")


def _difflines(a, b):
    """改行の差を除いた `diff` の行数(どちらか一方にしか無い行の合計)。"""
    import difflib
    la = _norm(a).decode("utf-8").splitlines()
    lb = _norm(b).decode("utf-8").splitlines()
    return sum(1 for x in difflib.ndiff(la, lb) if x[:1] in "+-")


def _local_imports(path, available):
    """`path` が import しているもののうち、**公開側に置いていないラボのモジュール**を返す。

    ★2026-09-04 新設。公開側の `test_char_counter.py` は `x_post`(ラボ側だけ)を、
    `test_jsblank.py` は1つ上の `jsblank` を import していて、**どちらも公開して以来
    1行も動いていなかった**。9/3 未明に `tools/` 側で直したのと同じ形の tests 版。

    ⚠ 見分けが要るものが2つある。どちらも「動く」ので鳴らしてはいけない:
      - `tools/tests/` から `sys.path` に**1つ上**を足して `tools/` のものを読む形
        (`test_jsblank` → `tools/jsblank.py`)。よって在庫は tests と tools の両方で見る
      - `try: import … except ImportError:` で**無いときの振る舞いが書いてある**形
        (`test_char_counter` の投稿ゲート)。無いことが分かっていて、無いと名乗って飛ばす
    """
    import ast
    lab = {p.stem for p in HERE.glob("*.py")} | {p.stem for p in ASSETS_DIR.glob("*.py")}
    tree = ast.parse(path.read_text(encoding="utf-8"))
    guarded = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Try) and any(
                (h.type is None) or "ImportError" in ast.dump(h.type) for h in n.handlers):
            for b in n.body:
                for x in ast.walk(b):
                    guarded.add(getattr(x, "lineno", None))
    out = []
    for n in ast.walk(tree):
        names = []
        if isinstance(n, ast.Import):
            names = [a.name.split(".")[0] for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            names = [n.module.split(".")[0]]
        for m in names:
            if m in lab and m not in available and n.lineno not in guarded:
                out.append((m, n.lineno))
    return out


def table_shape(txt):
    """(5) README の表が**表として成立しているか**(2026-09-04 昼 新設)。

    (4) は「表の行に名前が在るか」しか見ない。**名前は在るのに表が壊れている**形が
    実在した: セルの中に**生の改行**が入っていて(改行そのものを ``…`` で囲もうとした)、
    `test_regex_tester` の行が途中で切れ、続きの断片が表の外に落ちていた。
    GitHub では**その行が尻切れになり、以降が本文として出る**。名前は全部在るので (4) は通る。

    見るのは3つ。どれも「読む人の画面で表がどう出るか」に直に効くものだけ:
      (a) 表の領域(見出し行〜次の空行)に、`|` で始まらない行が混ざっていないか
      (b) 各行のセルの数が見出しと同じか(区切りの `|` を数える。`` ` `` の中と `\\|` は除く)
      (c) 行が `|` で終わっているか
    """
    lines = txt.split("\n")
    out = []
    heads = [i for i, l in enumerate(lines)
             if l.startswith("|") and i + 1 < len(lines)
             and re.match(r"^\|[\s:|-]+\|\s*$", lines[i + 1])]
    for h in heads:
        end = next((i for i in range(h, len(lines)) if lines[i].strip() == ""), len(lines))
        want = _cells(lines[h])
        for i in range(h, end):
            l = lines[i]
            if not l.startswith("|"):
                out.append("★ README の表が壊れている: %d 行目が `|` で始まらない"
                           "(セルの中に生の改行が入っていないか) — %r" % (i + 1, l[:40]))
                continue
            if not l.rstrip().endswith("|"):
                out.append("★ README の表が壊れている: %d 行目が `|` で終わっていない" % (i + 1))
                continue
            n = _cells(l)
            if n != want:
                out.append("★ README の表が壊れている: %d 行目のセルが %d 個(見出しは %d 個)"
                           % (i + 1, n, want))
    return out


def _cells(line):
    """行の区切りの `|` を数えてセルの数を出す。`` ` `` の中と `\\|` は区切りではない。"""
    n, tick, i = 0, False, 0
    s = line.strip()
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "`":
            tick = not tick
        elif c == "|" and not tick:
            n += 1
        i += 1
    return max(n - 1, 0)


def check_tests(dest):
    """`tools/tests/` を見る。**写しはしない**(意図的な差があるので手で写す)。

    見るのは5つ:
      (1) 差が `TESTS_DIFF_OK` に書いた行数と合っているか(=そこ以外が動いていないか)
      (2) 公開側が import しているものが公開側に**在るか**(動かない検証を置いていないか)
      (3) 手元にあって公開側に無い本が `TESTS_NOT_PUBLISHED` に理由つきで書いてあるか
      (4) 公開側の README が全部を載せているか
      (5) その README の表が**表として成立しているか**(2026-09-04 昼に追加)
    """
    tdir = dest / TESTS_DIR_NAME
    if not tdir.is_dir():
        print("tests: 公開側に %s が無い" % tdir)
        return 0
    pub = sorted(tdir.glob("*.py"))
    # 在庫は tests と**1つ上の `tools/`** の両方(`sys.path` に上を足す本があるため)
    avail = {p.stem for p in pub} | {p.stem for p in dest.glob("*.py")}
    same, diff_ok, bad, orphan = 0, 0, [], []
    for p in pub:
        src = HERE / TESTS_RENAMED_OK.get(p.name, p.name)
        if not src.exists():
            orphan.append(p.name)
            continue
        if _norm(src) == _norm(p):
            same += 1
            if p.name in TESTS_DIFF_OK:
                bad.append("★ 差が無くなった(TESTS_DIFF_OK から消すこと): tests/%s" % p.name)
            continue
        n = _difflines(src, p)
        want = TESTS_DIFF_OK.get(p.name)
        if want is None:
            bad.append("★ 写し忘れ(差 %d 行): tests/%s — 手元が原本。写すか、意図的なら "
                       "TESTS_DIFF_OK に行数と理由を書くこと" % (n, p.name))
        elif n != want[0]:
            bad.append("★ 意図した差から動いた: tests/%s は %d 行のはずが %d 行(%s)"
                       % (p.name, want[0], n, want[1]))
        else:
            diff_ok += 1

    # (2) import の連れ
    miss = []
    for p in pub:
        for m, ln in _local_imports(p, avail):
            miss.append("★ 公開側で動かない: tests/%s:%d が `%s` を import しているが "
                        "公開側に無い" % (p.name, ln, m))

    # (3) 手元にあって公開側に無い本
    unpub = []
    for src in sorted(HERE.glob("test_*.py")):
        if src.name in avail_names(pub) or src.name in TESTS_RENAMED_OK.values():
            continue
        if src.name in TESTS_NOT_PUBLISHED:
            continue
        unpub.append("★ 手元にあって公開側に無い: %s — 出すか、"
                     "TESTS_NOT_PUBLISHED に理由を書くこと" % src.name)

    # (4) README の載せ漏れ
    # ⚠ 最初は「README のどこかに名前があるか」で見ていたが、**それでは緩すぎた**。
    #   使い方の例(`python tools/tests/test_cron.py …`)にも名前が出るので、
    #   **表の行を丸ごと消しても鳴らなかった**(空振り確認で判明。今日2件目の
    #   「壊して鳴るかだけ見ていると、何にでも鳴る検査が満点を取る」)。
    #   → 検証(`test_*.py`)は**表の行**に在ることを見る。helper と参照データの
    #     作成器は表に出さないので、どこかに在ればよい。
    readme = tdir / "README.md"
    lost = []
    if readme.exists():
        txt = readme.read_text(encoding="utf-8")
        rows = "\n".join(ln for ln in txt.splitlines() if ln.startswith("|"))
        for p in pub:
            if p.name in ("skipwatch.py", "make_qr_reference.py"):
                if p.name not in txt:
                    lost.append("・README が名前も出していない: tests/%s" % p.name)
            elif p.name not in rows:
                lost.append("・README の表に無い: tests/%s(使い方の例にあるだけでは足りない)"
                            % p.name)
        lost += table_shape(txt)

    print("tests: 見た %d 本 / 一致 %d 本 / 意図した差 %d 本(既知 %d) / 手元に同名が無い %d 本"
          % (len(pub), same, diff_ok, len(TESTS_DIFF_OK), len(orphan)))
    for m in bad + miss + unpub:
        print("  " + m)
    for m in lost:
        print("  " + m)
    for n in orphan:
        print("  ★ 手元に同名が無い: tests/%s(名前が違うなら TESTS_RENAMED_OK に足す)" % n)
    return 1 if (bad or miss or unpub or orphan or lost) else 0


def avail_names(pub):
    return {p.name for p in pub}


def sabotage(dest):
    """(5) の空振り確認。**現物は書き換えず**、読んだ文字列を壊して鳴るかだけを見る。

    ⚠ 4つめは「**鳴ってはいけない形**」(2026-09-04 未明の申し送り)。
    壊して鳴るかだけを見ていると、**何にでも鳴る検査が満点を取る**。
    """
    txt = (dest / TESTS_DIR_NAME / "README.md").read_text(encoding="utf-8")
    lines = txt.split("\n")
    h = next(i for i, l in enumerate(lines) if l.startswith("| スクリプト |"))
    row = next(i for i in range(h + 2, len(lines)) if lines[i].startswith("|"))

    def cut(i, at):        # セルの中に生の改行を入れる(今日の実バグと同じ形)
        s = lines[i]
        return lines[:i] + [s[:at], s[at:]] + lines[i + 1:]

    cases = [
        ("セルの中に生の改行", "\n".join(cut(row, 60)), True),
        ("行末の `|` が落ちる", "\n".join(lines[:row] + [lines[row].rstrip()[:-1]]
                                        + lines[row + 1:]), True),
        ("セルが1つ増える", "\n".join(lines[:row] + [lines[row] + " 余り |"]
                                    + lines[row + 1:]), True),
        ("★鳴ってはいけない: `|` を `` ` `` の中に書いた正しい行",
         "\n".join(lines[:row] + [lines[row][:-1] + "(`a|b` のような書き方) |"]
                   + lines[row + 1:]), False),
    ]
    bad = 0
    for name, broken, want in cases:
        rang = bool(table_shape(broken))
        ok = (rang == want)
        bad += 0 if ok else 1
        print("%s %s → %s" % ("○" if ok else "×", name,
                              "鳴った" if rang else "鳴らない"))
    print("空振り確認: %d/%d" % (len(cases) - bad, len(cases)))
    return 1 if bad else 0


def targets():
    names = sorted(p.name for p in HERE.glob("make_en_*.py"))
    return [(HERE, n) for n in names + HELPERS] + [(ASSETS_DIR, n) for n in ASSETS]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=str(DEFAULT_REPO))
    ap.add_argument("--check", action="store_true", help="写さずに、ずれているものを並べるだけ")
    ap.add_argument("--sabotage", action="store_true",
                    help="README の表をわざと壊して、(5) が鳴るかを見る(現物は書き換えない)")
    a = ap.parse_args(argv)

    dest = pathlib.Path(os.path.expanduser(a.repo)) / "tools"
    if not dest.is_dir():
        sys.exit("× tools が無い: %s" % dest)

    if a.sabotage:
        return sabotage(dest)

    missing_src, stale, added, same = [], [], [], 0
    for where, name in targets():
        src = where / name
        if not src.exists():
            missing_src.append(name)
            continue
        dst = dest / name
        want = src.read_bytes()
        if not dst.exists():
            added.append(name)
        elif dst.read_bytes() != want:
            stale.append(name)
        else:
            same += 1
            continue
        if not a.check:
            shutil.copyfile(src, dst)

    for name in missing_src:
        print("× 手元に無い(HELPERS の綴り違い?): %s" % name)
    for name in added:
        print("%s 公開側に無かった: %s" % ("+" if not a.check else "★", name))
    for name in stale:
        print("%s 公開側が古い: %s" % ("↻" if not a.check else "★", name))
    print("揃っていた: %d 本 / 直した対象: %d 本" % (same, len(added) + len(stale)))

    # ★2026-09-03 追加: 写した先が **import で落ちないか**を静的に見る。
    #   `en_common.py`(9/2)と `en_pages.py`(9/3)は、どちらも
    #   「helper を1本化したので、写し忘れると公開側が動かなくなる」形だった。
    #   そのたびに HELPERS へ手で足すと、いつか足し忘れる = ここまでの話と同じ轍。
    #   → **写す対象が import している手元のモジュールが、全部写されているか**を数える。
    #     実行はしない(読むだけ)。
    listed = set(targets())
    names = {n for _, n in listed}
    # ★assets のぶんも「手元のモジュール」に数える(regen_ogp が make_ogp を import する)
    local = {p.stem for p in HERE.glob("*.py")} | {p.stem for p in ASSETS_DIR.glob("*.py")}
    lack = []
    for where, name in sorted(listed, key=lambda t: t[1]):
        src = where / name
        if not src.exists():
            continue
        text = src.read_text(encoding="utf-8", errors="replace")
        used = set(re.findall(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)",
                              text, re.M))
        for mod in sorted(used & local):
            if mod + ".py" not in names:
                lack.append("%s が import する %s.py が公開側に無い" % (name, mod))
    for msg in lack:
        print("★ " + msg)
    print("import の連れ: 写す %d 本すべてについて、手元のモジュールの写し漏れ %d 件"
          % (len(listed), len(lack)))

    tests_ng = check_tests(dest)

    if missing_src or lack or tests_ng:
        return 1
    if a.check and (added or stale):
        print("→ `python lab/scripts/sync_tools_mirror.py` で揃うこと")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
