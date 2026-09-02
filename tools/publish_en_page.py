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
7. **足し戻し6項目の確認**(2026-09-02 夜 追加。下記)

## ★2026-09-02 夜に足した 7(足し戻しの確認)

1〜6 は「ページを作る手順」だけを見ていて、**そのページをサイトに繋ぐ側**を1つも見ていなかった。
繋ぐ側は6項目あり、**そのどれもが、抜けても既存の検査に掛からない**:

| 項目 | 抜けたときに起きること | 既存の検査に掛かるか |
|---|---|---|
| hreflang(日英の両側) | 検索エンジンが別の言語の版を知らない | 片側だけなら掛かる。**両方無ければ掛からない** |
| 言語リンク(ナビの最後) | 読者がもう一方の版に行けない | hreflang があれば掛かる。**無ければ掛からない** |
| sitemap | 新しいページが載らない | 掛かる |
| 英語OGP画像 | SNS のカードが日本語のまま | **掛からない**(og:image が実在すれば通る) |
| `en/index.html` のカード | 一覧から辿れない | **掛からない**(ナビにあれば孤立にならない) |
| `check_en_parity` への登録 | **その後ずっと日英の食い違いを見ない** | **掛からない**(9/2 夜に是正するまで、これ自体が黙っていた) |

実際 8/28 に `base64`・`qr` で言語リンクが、9/2 朝に `pattern` で `en/index` のカードが漏れた。
どれも「作る側」は成功していて、繋ぐ側だけが抜けている。

使い方:
  python publish_en_page.py --slug unit \
    --jp-link '<li><a href="../unit/">単位換算</a></li>' \
    --en-link '<li><a href="./unit.html">Unit Converter</a></li>'

  python publish_en_page.py --slug unit ... --from-step 5   # 途中から
  python publish_en_page.py --regen-only                    # 5 だけ(健康診断として単体で使える)
  python publish_en_page.py --slug unit --wiring-only       # 7 だけ(足し戻しの確認)
"""
import argparse
import os
import pathlib
import re
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


def wiring(docs, slug):
    """足し戻し6項目を数える。(結果の行, 足りない数) を返す(2026-09-02 夜 新設)。

    ⚠ **見ていない範囲を最後に必ず出す**(9/1〜9/2に「見ていないことを黙る」検査が4件出たため)。
    """
    sys.path.insert(0, str(HERE))
    from check_en_parity import PAIRS, GENERATED     # noqa: E402  対応表は1か所だけ

    en_name = next((n for n, ja in PAIRS.items() if ja == f"{slug}/index.html"), None)

    lines, missing = [], 0

    def ok(cond, label, how):
        nonlocal missing
        lines.append(("  ✅ " if cond else "  ★ ") + label + ("" if cond else " … " + how))
        if not cond:
            missing += 1

    ok(en_name is not None, "check_en_parity.py の PAIRS に登録",
       f'PAIRS に "<英語ファイル名>": "{slug}/index.html" を足す')
    if en_name is None:
        lines.append("  (英語ファイル名が分からないので、残りは見ていない)")
        return lines, missing

    ja_p, en_p = docs / slug / "index.html", docs / "en" / en_name
    if not en_p.exists():
        ok(False, "英語ページが存在", f"{en_p} が無い")
        return lines, missing
    ja, en = ja_p.read_text(encoding="utf-8"), en_p.read_text(encoding="utf-8")

    # ⚠ `rel="alternate"` まで見ること(2026-09-02 夜の空振り確認で分かった)。
    #   最初 `hreflang="en" href="…"` の並びだけを見ていたので、`rel` を別の値に
    #   書き換えた仕込みが**素通り**した。`rel` が違えば hreflang の宣言では無いので、
    #   「hreflang がある」と言うのは嘘になる。
    def alt(text, lang, href):
        return f'<link rel="alternate" hreflang="{lang}" href="{href}">' in text
    ok(alt(ja, "en", f"{SITE}en/{en_name}") and alt(en, "ja", f"{SITE}{slug}/"),
       "hreflang が日英の両側にある", "両方のページの <head> に alternate を足す")
    ok("English version" in ja and ("Japanese version" in en or "日本語版" in en),
       "ナビの言語リンクが日英の両側にある", "fix_lang_link.py を回す")
    sm = (docs / "sitemap.xml").read_text(encoding="utf-8")
    ok(f"{SITE}en/{en_name}" in sm, "sitemap に載っている", "sitemap.xml に <url> を足す")
    # ★OGP は**名前の型を決め打ちにしない**(2026-09-02 夜。最初そうしたら誤検出が4件出た)。
    #   古い4本(regex-tester / char-counter / palette / timezone)は `ogp-en-<名>.png`、
    #   あとの18本は `ogp-<名>-en.png` で、**命名が2通りある**。
    #   名前を当てにいくのではなく、**ページが実際に指しているURLを読んで**
    #   (a) その画像が実在するか (b) 日本語版と別の画像か、の2つを見る。
    #   ★この誤検出は「新しい検査を書いたら、まず既存の全部に当てる」で見つかった。
    #     take-home 1本だけで確かめていたら、正しいものを間違いと呼ぶ道具ができていた。
    def og_of(text):
        m = re.search(r'<meta property="og:image" content="([^"]+)"', text)
        return m.group(1) if m else None
    og_en, og_ja = og_of(en), og_of(ja)
    og_ok = bool(og_en) and og_en != og_ja and og_en.startswith(SITE) \
        and (docs / og_en[len(SITE):]).exists()
    ok(og_ok, "英語のOGP画像がある(日本語版と別・ファイルが実在)",
       f'tools/make_ogp.py {en_name[:-len(".html")]}-en "<題>" "<説明>" で作る')
    ok(f'href="./{en_name}"' in (docs / "en" / "index.html").read_text(encoding="utf-8"),
       "en/index.html にカードがある", "英語トップに <a class=\"card\"> を足す")
    # ⚠ ここは合否にしない。生成器を持つかどうかは事実の申告であって、
    #    どちらでも正しい状態がある(手書きは char-counter / timezone の2本)。
    #    「常に真の検査」を足すと ✅ の数だけ増えて中身が減るので、事実として出すだけにする。
    lines.append("  （%s は check_en_parity で「%s」として扱われる）"
                 % (en_name, "生成" if en_name in GENERATED else "手書き"))
    lines.append("  見ていない範囲: 訳の質 / 画面の見た目 / 日本語トップのカード"
                 "(日本語ページは先にあるので今回は対象外)")
    return lines, missing


SITE = "https://hirulab-dev.github.io/hirulab-tools/"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", help="日本語ページのスラッグ(例: unit)")
    ap.add_argument("--jp-link", help="日本語ページのナビに足す <li>…</li> そのもの")
    ap.add_argument("--en-link", help="英語ページのナビに足す <li>…</li> そのもの")
    ap.add_argument("--repo", default=str(DEFAULT_REPO))
    ap.add_argument("--from-step", type=int, default=1)
    ap.add_argument("--regen-only", action="store_true", help="5 だけ回す(健康診断)")
    ap.add_argument("--wiring-only", action="store_true",
                    help="7 だけ回す(足し戻し6項目の確認。--slug が要る)")
    a = ap.parse_args(argv)

    repo = pathlib.Path(os.path.expanduser(a.repo))
    docs = repo / "docs"
    if not docs.is_dir():
        sys.exit(f"× docs が無い: {docs}")
    first = 5 if a.regen_only else a.from_step
    last = 6 if a.regen_only else 7
    if a.wiring_only:
        first, last = 7, 7
        if not a.slug:
            sys.exit("× --wiring-only には --slug が要る")

    if first <= 1 <= last:
        step(1, "作業ツリーが clean か")
        dirty = git(repo, "status", "--porcelain")
        if dirty:
            print("  ⚠ 未コミットの変更がある。5 の判定が読めなくなるので、"
                  "先に commit するか、ここで何が動いたかを自分で覚えておくこと:")
            print("  " + dirty.replace("\n", "\n  "))
        else:
            print("  clean")

    if first <= 2 <= last:
        if not a.slug:
            sys.exit("× --slug が要る")
        gen = f"make_en_{a.slug.replace('-', '_')}.py"
        step(2, f"{gen} を走らせる")
        if not (HERE / gen).exists():
            sys.exit(f"× 生成スクリプトが無い: {gen}(先に書くこと)")
        rc, _ = run([gen, str(docs)])
        if rc:
            sys.exit("× 生成に失敗した(訳し忘れ・日英のコード不一致など。上の出力を読む)")

    if first <= 3 <= last:
        if not (a.jp_link and a.en_link):
            sys.exit("× --jp-link と --en-link が要る")
        step(3, "実ページ全部のナビに1行足す(add_tool_link.py)")
        rc, _ = run(["add_tool_link.py", "--docs", str(docs),
                     "--jp-link", a.jp_link, "--en-link", a.en_link,
                     "--skip", a.slug, "--skip-en", f"{a.slug}.html"])
        if rc:
            sys.exit("× add_tool_link に失敗")

    if first <= 4 <= last:
        step(4, "生成元を実ページから同期し、英語ナビにも足す(sync_en_nav.py --add-en)")
        rc, _ = run(["sync_en_nav.py", "--docs", str(docs), "--add-en", a.en_link])
        if rc:
            sys.exit("× sync_en_nav に失敗")

    if first <= 5 <= last:
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

    if first <= 6 <= last:
        step(6, "通し検査")
        rc1, _ = run(["check_site.py", "--docs", str(docs), "--local"])
        rc2, _ = run(["check_contrast.py", "--docs", str(docs)])
        if rc1 or rc2:
            sys.exit("× 通し検査に引っかかった")
        print("  通し検査 OK")

    if first <= 7 <= last:
        step(7, "足し戻し6項目の確認")
        if not a.slug:
            print("  --slug が無いので飛ばした(足し戻しは1本ずつしか見られない)")
        else:
            lines, n = wiring(docs, a.slug)
            for ln in lines:
                print(ln)
            if n:
                sys.exit("× 足し戻しが %d 項目足りない(上の ★ を潰すこと)" % n)

    print("\n✅ 手順は最後まで通った。push は git_push_tools.py で。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
