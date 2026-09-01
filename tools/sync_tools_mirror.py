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
- `tools/` にしか無いもの(`make_ogp.py` など公開用の道具)は触らない
- `tools/tests/` は別管理(検証スクリプト。従来どおり各回の作業で足す)

    python lab/scripts/sync_tools_mirror.py            # 揃える
    python lab/scripts/sync_tools_mirror.py --check    # 見るだけ(ずれていたら終了コード1)
"""
import argparse
import os
import pathlib
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
    "add_tool_link.py",   # 実ページ全部のナビに1行足す
    "sync_en_nav.py",     # 生成元を実ページから同期する
    "fix_lang_link.py",   # もう一方の言語への行を1本だけ最後に置く
    "check_en_parity.py",  # 日英の食い違いを見張る
    "publish_en_page.py",  # 英語版を1本出すときの正しい順番
    "sync_tools_mirror.py",  # これ自身。README がこの道具を名指すので、現物も置いておく
]


def targets():
    names = sorted(p.name for p in HERE.glob("make_en_*.py"))
    return names + HELPERS


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
    for name in targets():
        src = HERE / name
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

    if missing_src:
        return 1
    if a.check and (added or stale):
        print("→ `python lab/scripts/sync_tools_mirror.py` で揃うこと")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
