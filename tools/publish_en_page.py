#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""英語版のページを1本出すときの手順を、順番ごと道具にしたもの。

2026-08-31 夜 新設。8/31 昼枠の「詰まったこと」の根治:

> `make_en_*.py` を全部走らせ直すのは、今の作りでは安全ではない。
> 静的ナビを持つ生成元は `--add-en` を回さない限り古いままなので、走らせ直すと現物より減る。

その正しい順番が**俺の頭の中にしかなかった**。順番を間違えると、
`sync_en_nav` が古い現物を生成元に写して固定してしまう(password の JS 配列で実際に一往復した)。
**手で書き直せる形にしない**(同じ日の security-policy 原則10と同じ考え方)。

## 正しい順番(この道具がこの順で回す)

1. 作業ツリーが clean か見る(でないと 5 の「再生成で何が動いたか」が読めない)
2. `make_en_<slug>.py` を走らせて英語ページを書き出す
3. `add_tool_link.py` で**実ページ全部**のナビに新しい道具の1行を足す
4. `sync_en_nav.py --add-en` で**生成元**を実ページから同期し、英語ナビにも足す
5. `make_en_*.py` を**全部**走らせ直す → **新しいページ以外が動いたら止めて報告**
   (動いたら、それは「生成元が実ページより古い」という傷が出た証拠)
6. 通し検査(`check_site.py --local` と `check_contrast.py`)

使い方:
  python publish_en_page.py --slug unit \
    --jp-link '<li><a href="../unit/">単位換算</a></li>' \
    --en-link '<li><a href="./unit.html">Unit Converter</a></li>'

  python publish_en_page.py --slug unit ... --from-step 5   # 途中から
  python publish_en_page.py --regen-only                    # 5 だけ(健康診断として単体で使える)
"""
import argparse
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_REPO = pathlib.Path(os.path.expanduser("~/hirulab-tools"))


def run(args, cwd=None, quiet=False):
    p = subprocess.run([sys.executable, *args] if args[0].endswith(".py") else args,
                       cwd=str(cwd or HERE), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    if not quiet and out:
        print("  " + out.replace("\n", "\n  "))
    return p.returncode, out


def git(repo, *args):
    p = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return (p.stdout or "").strip()


def generators():
    return sorted(p.name for p in HERE.glob("make_en_*.py"))


def step(n, title):
    print(f"\n=== {n}. {title} ===")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", help="日本語ページのスラッグ(例: unit)")
    ap.add_argument("--jp-link", help="日本語ページのナビに足す <li>…</li> そのもの")
    ap.add_argument("--en-link", help="英語ページのナビに足す <li>…</li> そのもの")
    ap.add_argument("--repo", default=str(DEFAULT_REPO))
    ap.add_argument("--from-step", type=int, default=1)
    ap.add_argument("--regen-only", action="store_true", help="5 だけ回す(健康診断)")
    a = ap.parse_args(argv)

    repo = pathlib.Path(os.path.expanduser(a.repo))
    docs = repo / "docs"
    if not docs.is_dir():
        sys.exit(f"× docs が無い: {docs}")
    first = 5 if a.regen_only else a.from_step

    if first <= 1:
        step(1, "作業ツリーが clean か")
        dirty = git(repo, "status", "--porcelain")
        if dirty:
            print("  ⚠ 未コミットの変更がある。5 の判定が読めなくなるので、"
                  "先に commit するか、ここで何が動いたかを自分で覚えておくこと:")
            print("  " + dirty.replace("\n", "\n  "))
        else:
            print("  clean")

    if first <= 2:
        if not a.slug:
            sys.exit("× --slug が要る")
        gen = f"make_en_{a.slug.replace('-', '_')}.py"
        step(2, f"{gen} を走らせる")
        if not (HERE / gen).exists():
            sys.exit(f"× 生成スクリプトが無い: {gen}(先に書くこと)")
        rc, _ = run([gen, str(docs)])
        if rc:
            sys.exit("× 生成に失敗した(訳し忘れ・日英のコード不一致など。上の出力を読む)")

    if first <= 3:
        if not (a.jp_link and a.en_link):
            sys.exit("× --jp-link と --en-link が要る")
        step(3, "実ページ全部のナビに1行足す(add_tool_link.py)")
        rc, _ = run(["add_tool_link.py", "--docs", str(docs),
                     "--jp-link", a.jp_link, "--en-link", a.en_link,
                     "--skip", a.slug, "--skip-en", f"{a.slug}.html"])
        if rc:
            sys.exit("× add_tool_link に失敗")

    if first <= 4:
        step(4, "生成元を実ページから同期し、英語ナビにも足す(sync_en_nav.py --add-en)")
        rc, _ = run(["sync_en_nav.py", "--docs", str(docs), "--add-en", a.en_link])
        if rc:
            sys.exit("× sync_en_nav に失敗")

    if first <= 5:
        step(5, "生成スクリプトを全部走らせ直す(新しいページ以外が動いたら傷)")
        before = git(repo, "status", "--porcelain")
        for gen in generators():
            rc, out = run([gen, str(docs)], quiet=True)
            if rc:
                print(f"  × {gen} が失敗した:\n  " + out.replace("\n", "\n  "))
                sys.exit("× 再生成で止まった")
        after = git(repo, "status", "--porcelain")
        moved = sorted(set(after.split("\n")) - set(before.split("\n")))
        moved = [m for m in moved if m.strip()]
        expect = f"{a.slug}.html" if a.slug else None
        surprise = [m for m in moved if not (expect and expect in m)]
        print(f"  生成スクリプト {len(generators())} 本を走らせた")
        if surprise:
            print("  ★ 新しいページ以外が動いた(＝生成元が実ページより古かった):")
            for m in surprise:
                print("    " + m)
            print("  → 中身を確かめること。ナビの行が減っていたら sync_en_nav --add-en の回し忘れ")
        else:
            print("  動いたのは新しいページだけ(生成元は実ページと揃っている)")

    if first <= 6:
        step(6, "通し検査")
        rc1, _ = run(["check_site.py", "--docs", str(docs), "--local"])
        rc2, _ = run(["check_contrast.py", "--docs", str(docs)])
        if rc1 or rc2:
            sys.exit("× 通し検査に引っかかった")
        print("  通し検査 OK")

    print("\n✅ 手順は最後まで通った。push は git_push_tools.py で。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
