#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""フリマ利益計算機( docs/frima-profit/ )の検証。2026-09-01 夜に新設。

★**2026-08-15 公開の道具なのに、検証が1本も無かった**(10本目。これで「検証の無い道具」は
  正規表現テスタの1本を残すだけになる)。take-home と同じくお金の計算なので、
  直す前にまず**いまの振る舞いを固定する**のが先。

## 参照をどこから取るか

take-home と同じで、**第三者の実装という参照が無い**(フリマの手取り計算に標準実装は無い)。
そこで参照を役目で分ける。

| 見るもの | 参照 | どこから来たか |
|---|---|---|
| 利益・利益率・損益分岐・許容作業時間 | 画面が宣言している式を Python に書き直したもの | 道具が自分で宣言している前提 |
| **損益分岐の売値** | **式ではなく性質で見る** — その売値なら利益が0以上、1円下なら赤字 | 道具のコードと無関係 |
| 表示 | 描かれた4枚のカードと内訳の文を読み戻す(¥ と桁区切りをほどく) | 道具自身 |
| **内訳の足し算** | **画面に出ている数字だけを足し引きする** | 道具自身(下に理由) |

⚠ 上2つは「同じ前提を2回書いているだけ」なので、測れるのは**「宣言どおりに動いているか」**だけ。
   そう書いておく(take-home の検証の冒頭に書いたのと同じ断り)。

★ **3つめの「損益分岐」だけは、道具の式を写さずに済む。** 「その売値で売ったら赤字にならず、
   1円下げたら赤字になる」は式ではなく**性質**なので、参照を別の出どころから取れたことになる。

★ **4つめが、この検証でいちばん効いた。** 画面には「内訳: 売値 A − 手数料 B − 送料 C
   − 仕入れ D = E」という文が出る。**A〜E は全部その場で丸めて表示している**ので、
   利用者はこの行を読んで足し算を検算できてしまう。なので**式ではなく、
   表示された数字そのものが辻褄が合うか**を見る。

## ★この検証で見つけたこと(2026-09-01)

**内訳の行が、足しても合計にならない場合がある。** 手数料は小数のまま利益に効くのに、
表示だけ四捨五入するので、丸めの端数が合計にだけ乗る。
例: 売値2,005円・手数料10%・送料210・仕入れ500・振込200 のとき、画面は
「¥2,005 − ¥201 − ¥210 − ¥500 − ¥200 = ¥895」と出る。**左辺を足すと894。**
1円だが、**利用者が電卓を持たずに検算できてしまう場所**で1円合わない(=そこだけ見ると
道具が壊れているように見える)。しかもフリマの手数料は本来 **円未満切り捨て**なので、
「丸めを表示にだけ効かせる」のは実務とも合っていない。

使い方:
    python lab/scripts/test_frima_profit.py            # 手元のページ
    python lab/scripts/test_frima_profit.py --page <html>
    python lab/scripts/test_frima_profit.py --n 400
    python lab/scripts/test_frima_profit.py --sabotage
"""
import argparse
import asyncio
import math
import pathlib
import random
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
from playwright.async_api import async_playwright  # noqa: E402

DEFAULT_PAGE = pathlib.Path.home() / "hirulab-tools" / "docs" / "frima-profit" / "index.html"

FIELDS = ["price", "cost", "ship", "pack", "feePct", "payout"]


# ── 参照(画面が宣言している式を、道具のコードを見ずに書き直したもの) ──────────────

def model(price, cost, ship, pack, feePct, payout):
    fee_pct = feePct
    # 販売手数料は円未満切り捨て(2026-09-01 にこう直した。理由はこのファイルの冒頭)
    fee = math.floor(price * fee_pct / 100)
    profit = price - fee - ship - cost - pack - payout
    margin = profit / price * 100 if price > 0 else None
    fixed = ship + cost + pack + payout
    breakeven = None
    if fee_pct < 100:
        breakeven = math.ceil(fixed / (1 - fee_pct / 100))
        while breakeven > 0 and \
                (breakeven - 1) - math.floor((breakeven - 1) * fee_pct / 100) - fixed >= 0:
            breakeven -= 1
    worktime = math.floor(profit / 1000 * 60) if profit > 0 else 0
    return dict(fee=fee, profit=profit, margin=margin, fixed=fixed,
                breakeven=breakeven, worktime=worktime)


def js_round(x):
    """JS の Math.round は「.5 は常に上」(Python の round は偶数丸め)。"""
    return math.floor(x + 0.5)


def yen(n):
    """道具の yen() と同じ書き方に整える(符号 → ¥ → 桁区切り)。"""
    return ("-" if n < 0 else "") + "¥" + format(abs(js_round(n)), ",")


def unyen(s):
    """画面の ¥1,234 / -¥1,234 を数に戻す。"""
    m = re.fullmatch(r"(-?)¥([\d,]+)", s.strip())
    if not m:
        return None
    return (-1 if m.group(1) else 1) * int(m.group(2).replace(",", ""))


# ── 見本 ────────────────────────────────────────────────────────

def make_cases(rng, n):
    cases = [
        # 手で置く: 境目と、実務でよくある形
        dict(price=2000, cost=500, ship=210, pack=0, feePct=10, payout=200),   # 既定値
        dict(price=0, cost=0, ship=0, pack=0, feePct=10, payout=0),            # 全部0
        dict(price=0, cost=500, ship=210, pack=0, feePct=10, payout=200),      # 売値0(利益率が —)
        dict(price=1000, cost=0, ship=0, pack=0, feePct=100, payout=0),        # 手数料100%(分岐が∞)
        dict(price=1000, cost=0, ship=0, pack=0, feePct=0, payout=0),          # 手数料0%
        dict(price=910, cost=500, ship=210, pack=0, feePct=10, payout=200),    # 利益ちょうど0近辺
        dict(price=300, cost=500, ship=210, pack=0, feePct=10, payout=200),    # 赤字
        dict(price=100000, cost=0, ship=0, pack=0, feePct=8.8, payout=0),      # 小数の料率
        # ★「薄い領域」対策: 手数料が .5 ちょうどになる売値(丸めの向きが出る)
        dict(price=2005, cost=500, ship=210, pack=0, feePct=10, payout=200),
        dict(price=1005, cost=0, ship=0, pack=0, feePct=10, payout=0),
        dict(price=15, cost=0, ship=0, pack=0, feePct=10, payout=0),
    ]
    while len(cases) < n:
        cases.append(dict(
            price=rng.choice([0, rng.randrange(0, 3000, 5), rng.randrange(0, 200000, 10)]),
            cost=rng.randrange(0, 5000, 10),
            ship=rng.choice([0, 175, 210, 350, 750, rng.randrange(0, 2000, 10)]),
            pack=rng.choice([0, 0, 20, 50, rng.randrange(0, 500, 10)]),
            feePct=rng.choice([0, 4.5, 5, 6, 8.8, 10, 10, 12.5, 20, 100]),
            payout=rng.choice([0, 200, 200, rng.randrange(0, 500, 10)]),
        ))
    return cases[:n]


class Report:
    def __init__(self):
        self.rows, self.bad = [], []

    def line(self, name, n, bad):
        self.rows.append((name, n, len(bad)))
        self.bad += [(name, b) for b in bad]

    def ok(self):
        return not self.bad

    def show(self, limit=8):
        print()
        print("| 見たもの | 件数 | 食い違い |")
        print("|---|---:|---:|")
        for name, n, b in self.rows:
            print("| %s | %s | %d |" % (name, format(n, ","), b))
        if self.bad:
            print("\n食い違いの中身(先頭 %d 件):" % limit)
            for name, b in self.bad[:limit]:
                print("  [%s] %s" % (name, b))
        print("\n食い違い合計: %d" % len(self.bad))


async def set_inputs(pg, c):
    for k in FIELDS:
        await pg.fill("#" + k, str(c[k]))
    # input イベントで更新が走る決まりなので、最後の1つで確実に発火させる
    await pg.dispatch_event("#price", "input")


async def read_screen(pg):
    return await pg.evaluate("""() => ({
        profit: document.getElementById('profit').textContent,
        cls: document.getElementById('profit').className,
        margin: document.getElementById('margin').textContent,
        breakeven: document.getElementById('breakeven').textContent,
        worktime: document.getElementById('worktime').textContent,
        breakdown: document.getElementById('breakdown').textContent
    })""")


async def check_cases(pg, rep, cases):
    bad_profit, bad_margin, bad_be, bad_wt, bad_sum, bad_cls = [], [], [], [], [], []
    for c in cases:
        m = model(**c)
        await set_inputs(pg, c)
        s = await read_screen(pg)
        tag = f"price={c['price']} fee={c['feePct']}% ship={c['ship']} cost={c['cost']} pack={c['pack']} payout={c['payout']}"

        if s["profit"] != yen(m["profit"]):
            bad_profit.append(f"{tag}: 利益 画面={s['profit']} 参照={yen(m['profit'])}")

        want_margin = "—" if m["margin"] is None else f"{m['margin']:.1f}%"
        # JS の toFixed も .5 は上に転がすので、Python 側も同じ向きで作る
        if m["margin"] is not None:
            want_margin = f"{math.floor(abs(m['margin']) * 10 + 0.5) / 10 * (1 if m['margin'] >= 0 else -1):.1f}%"
        if s["margin"] != want_margin:
            bad_margin.append(f"{tag}: 利益率 画面={s['margin']} 参照={want_margin}")

        # ★損益分岐は式を写さず「性質」で見る
        if m["breakeven"] is None:
            if s["breakeven"] != "—":
                bad_be.append(f"{tag}: 分岐 画面={s['breakeven']} 参照=—")
        else:
            got = unyen(s["breakeven"])
            if got is None:
                bad_be.append(f"{tag}: 分岐が読めない: {s['breakeven']}")
            else:
                here = model(got, c["cost"], c["ship"], c["pack"], c["feePct"], c["payout"])["profit"]
                below = model(got - 1, c["cost"], c["ship"], c["pack"], c["feePct"], c["payout"])["profit"]
                if here < -1e-9:
                    bad_be.append(f"{tag}: 分岐{got}円でも赤字({here:.4f})")
                elif below >= 0 and got > 0:
                    bad_be.append(f"{tag}: 分岐{got}円の1円下でも黒字({below:.4f})=切り上げすぎ")

        if s["worktime"] != f"{m['worktime']}分":
            bad_wt.append(f"{tag}: 作業時間 画面={s['worktime']} 参照={m['worktime']}分")

        want_cls = "value " + ("plus" if m["profit"] > 0 else "minus" if m["profit"] < 0 else "")
        if s["cls"].strip() != want_cls.strip():
            bad_cls.append(f"{tag}: 色 画面={s['cls']!r} 参照={want_cls!r}")

        # ★内訳の足し算: 画面に出ている数字だけで検算する
        nums = [unyen(x) for x in re.findall(r"-?¥[\d,]+", s["breakdown"])]
        if len(nums) < 3 or any(x is None for x in nums):
            bad_sum.append(f"{tag}: 内訳が読めない: {s['breakdown']}")
        else:
            shown_total = nums[-1]
            lhs = nums[0] - sum(nums[1:-1])
            if lhs != shown_total:
                bad_sum.append(f"{tag}: 内訳を足すと {lhs} だが「= {shown_total}」と出ている"
                               f" / {s['breakdown']}")

    n = len(cases)
    rep.line("利益(¥)", n, bad_profit)
    rep.line("利益率(%)", n, bad_margin)
    rep.line("損益分岐の売値(性質で判定)", n, bad_be)
    rep.line("許容作業時間(分)", n, bad_wt)
    rep.line("利益の色(黒字/赤字)", n, bad_cls)
    rep.line("★内訳の足し算が合計と合うか", n, bad_sum)


async def check_preset(pg, rep):
    """販売先を選ぶと手数料率が入れ替わるか。★同じ value の選択肢が3つある点も見る。"""
    bad = []
    opts = await pg.evaluate(
        """() => [...document.querySelectorAll('#preset option')]
                   .map(o => [o.value, o.dataset.fee ?? null, o.textContent])""")
    values = [v for v, _, _ in opts]
    dup = {v for v in values if values.count(v) > 1}
    if dup:
        # 読むだけなら害は無いが、`.value` で選び直す処理を足した瞬間に別の店が選ばれる
        bad.append(f"value が重複した選択肢がある: {sorted(dup)} — "
                   f"`.value` で選択を戻す処理を足すと別の販売先が選ばれる")
    for i, (v, fee, label) in enumerate(opts):
        before = await pg.input_value("#feePct")
        await pg.select_option("#preset", index=i)
        got = await pg.input_value("#feePct")
        if fee is None:
            # 「自分で入力」は率を書き換えないのが正しい
            if got != before:
                bad.append(f"{label}: 率を書き換えないはずなのに {before}→{got} と動いた")
            continue
        if float(got) != float(fee):
            bad.append(f"{label}: 選んでも手数料率が {got} のまま(期待 {fee})")
    rep.line("販売先プリセット", len(opts), bad)


async def check_over_100(pg, rep):
    """★手数料率に100を超える値を入れたとき、損益分岐が意味のある表示になるか。

    入力欄は max=100 だが、数値入力は max を超える値を打ててしまう(妥当性は落ちるが
    .value には入る)。1 - fee/100 が負になるので、分岐の売値が**負の金額**として出る。
    「¥-3,150 まで値下げすれば黒字」は読み手にとって意味を成さない。
    """
    bad = []
    await set_inputs(pg, dict(price=1000, cost=0, ship=210, pack=0, feePct=150, payout=200))
    s = await read_screen(pg)
    got = unyen(s["breakeven"])
    if got is not None and got < 0:
        bad.append(f"手数料150%で損益分岐が {s['breakeven']}(負の売値)と出る。"
                   f"どんな売値でも黒字にならないので「—」が正しい")
    rep.line("手数料率が100%を超えるとき", 1, bad)


async def run(html_path, n, seed, quiet=False):
    rng = random.Random(seed)
    cases = make_cases(rng, n)
    rep = Report()
    url = pathlib.Path(html_path).resolve().as_uri()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context()).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(url)
        await check_cases(pg, rep, cases)
        await check_preset(pg, rep)
        await check_over_100(pg, rep)
        if errs:
            rep.line("JSエラー", 0, errs)
        await b.close()
    if not quiet:
        rep.show()
    return rep


SABOTAGE = [
    ("手数料を売値に掛け忘れる",
     ("const fee = Math.floor(price * feePct / 100);", "const fee = Math.floor(feePct / 100);")),
    # ★直した当日の傷を守る: 手数料を切り捨てずに小数のまま持つと、内訳の行が合計と合わなくなる
    ("手数料の円未満切り捨てをやめる(9/1に直した傷)",
     ("const fee = Math.floor(price * feePct / 100);", "const fee = price * feePct / 100;")),
    ("利益から送料を引き忘れる",
     ("const profit = price - fee - ship - cost - pack - payout;",
      "const profit = price - fee - cost - pack - payout;")),
    ("利益率を売値でなく仕入れ値で割る",
     ("const margin = price > 0 ? profit / price * 100 : 0;",
      "const margin = price > 0 ? profit / (cost||1) * 100 : 0;")),
    ("損益分岐で手数料を考えない",
     ("breakeven = Math.ceil(fixed / (1 - feePct / 100));", "breakeven = Math.ceil(fixed);")),
    # ★下の2つは 2026-09-01 に入れた「切り捨てのぶん1円詰める」処理そのものを狙う。
    #   直した箇所を守る検査が要る(直した当日は通っても、次に触った人が戻せてしまう)
    ("損益分岐の詰め直しをやめる(1円高いまま出す)",
     ("    while (breakeven > 0 &&", "    while (false &&")),
    ("損益分岐を詰めすぎて赤字の売値を出す",
     ("Math.floor((breakeven - 1) * feePct / 100) - fixed >= 0",
      "Math.floor((breakeven - 1) * feePct / 100) - fixed >= -2")),
    ("許容作業時間を切り捨てでなく切り上げにする",
     ("Math.floor(mins) + \"分\"", "Math.ceil(mins) + \"分\"")),
    ("赤字でも黒字の色にする",
     ('(profit > 0 ? "plus" : profit < 0 ? "minus" : "")', '"plus"')),
    ("内訳の合計だけ別の値にする",
     ("` = ${yen(profit)}`", "` = ${yen(profit + 1)}`")),
    ("プリセットを選んでも手数料率を入れ替えない",
     ('if (fee !== undefined) $("feePct").value = fee;',
      'if (false) $("feePct").value = fee;')),
    ("「自分で入力」でも率を上書きしてしまう",
     ('if (fee !== undefined) $("feePct").value = fee;',
      '$("feePct").value = fee === undefined ? 0 : fee;')),
]


async def sabotage(html_path, n, seed):
    src = pathlib.Path(html_path).read_text(encoding="utf-8")
    tmp = pathlib.Path(html_path).with_name("_sabotage_frima.html")
    print("わざと壊して、検査が捕まえるか見る(%d 種)\n" % len(SABOTAGE))
    missed = []
    try:
        for i, (name, (a, b)) in enumerate(SABOTAGE, 1):
            if a not in src:
                print("%2d. %-40s ★仕込めない(差し替え元が見つからない)" % (i, name))
                missed.append(name)
                continue
            tmp.write_text(src.replace(a, b, 1), encoding="utf-8", newline="\n")
            rep = await run(tmp, max(40, n // 4), seed + i, quiet=True)
            if rep.ok():
                print("%2d. %-40s ★素通り" % (i, name))
                missed.append(name)
            else:
                print("%2d. %-40s 検出(%s)" % (i, name, sorted({x for x, _ in rep.bad})[0]))
    finally:
        if tmp.exists():
            tmp.unlink()
    print("\n素通り: %d / %d" % (len(missed), len(SABOTAGE)))
    for m in missed:
        print("  - " + m)
    return 1 if missed else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default=str(DEFAULT_PAGE))
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--sabotage", action="store_true")
    args = ap.parse_args()
    if args.sabotage:
        return asyncio.run(sabotage(args.page, args.n, args.seed))
    rep = asyncio.run(run(args.page, args.n, args.seed))
    return 0 if rep.ok() else 1


if __name__ == "__main__":
    sys.exit(main())
