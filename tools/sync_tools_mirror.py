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
- `tools/tests/` は別管理(検証スクリプト。従来どおり各回の作業で足す)

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


def targets():
    names = sorted(p.name for p in HERE.glob("make_en_*.py"))
    return [(HERE, n) for n in names + HELPERS] + [(ASSETS_DIR, n) for n in ASSETS]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=str(DEFAULT_REPO))
    ap.add_argument("--check", action="store_true", help="写さずに、ずれているものを並べるだけ")
    a = ap.parse_args(argv)

    dest = pathlib.Path(os.path.expanduser(a.repo)) / "tools"
    if not dest.is_dir():
        sys.exit("× tools が無い: %s" % dest)

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

    if missing_src or lack:
        return 1
    if a.check and (added or stale):
        print("→ `python lab/scripts/sync_tools_mirror.py` で揃うこと")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
