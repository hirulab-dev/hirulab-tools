#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手取り計算機( docs/take-home/ )を、独立に書いた模型と突き合わせる。2026-09-01 昼に新設。

★**2026-08-15 公開の道具なのに、検証が1本も無かった**(9本目)。
  お金の計算なので、直す前にまず**いまの振る舞いを固定する**のが先。

## 参照をどこから取るか

この道具には**第三者の実装という参照が無い**(日本の給与計算のライブラリを持ってきても、
どこまで入れるかの前提が違うので「一致するはず」にならない)。そこで参照は3つに分ける。

| 見るもの | 参照 | どこから来たか |
|---|---|---|
| 給与所得控除・所得税の速算表・復興特別所得税 | **国税庁の表を Python に書き下したもの** | 道具のコードを見ずに表から |
| 社会保険・住民税・手取りの組み立て | **画面に書いてある模型を Python に書き下したもの** | 道具が自分で宣言している前提 |
| 料率を書き換えたときの動き | **書き換えた値で参照を計算し直す** | この道具の看板機能なので必ず測る |
| 表示 | **描かれた表と合計を読み戻す**(¥ と桁区切りをほどく) | 道具自身 |

⚠ **「国税庁の表」だけは道具と別の出どころ**だが、社会保険と住民税の組み立ては
   道具が画面で宣言している近似そのものなので、**同じ前提を2回書いているだけ**である。
   ここは「正しさ」ではなく**「宣言どおりに動いているか」**しか測れない。そう書いておく。

## ★この検証で見つけて、同じ日に直したこと(2026-09-01)

**「うち賞与の合計」の入力欄が、結果を1円も変えなかった。** コードは値を読むが、
そのあと1度も使っていなかった。画面には賞与の欄があり、利用者は効くと思って入れる。
原因は**社会保険料に上限が無かったこと**で、月給と賞与に同じ料率を掛けるだけだったので、
どう割り振っても合計が同じになっていた。**欄そのものが宣言と矛盾していた**形。

同じ根っこで**もっと大きい間違い**もあった: 上限を見ないので、
**年収が高いほど実際より多く引かれていた**。年収2,000万(うち賞与400万・年2回)なら
厚生年金を **183万**と出していたが、上限を入れると **98.8万**(月給ぶん71.4万 + 賞与ぶん27.5万)。
**84万円、額面の4.2%**を多く引いていたことになる。

→ 上限を入れて直した。月給ぶんと賞与ぶんを分け、健保は「標準報酬月額139万」と
「賞与の年度累計573万」、厚年は「標準報酬月額65万」と「賞与の1回150万」で頭打ちにする。
賞与の**支給回数**の入力を足した(厚年の賞与の上限は1回あたりなので回数で変わる)。
上限も画面で直せる(「料率は全部あなたが直せます」という、この道具の方針に合わせた)。

⚠ **順番を守った**: 直す前にこの検証で「いまの振る舞い」を固定し、
  全部通ることを確かめてから計算を変えた。お金の計算なので、
  変わったことが分かる状態を先に作る。

使い方:
    python lab/scripts/test_take_home.py            # 手元のページ
    python lab/scripts/test_take_home.py --page <html>
    python lab/scripts/test_take_home.py --n 300
    python lab/scripts/test_take_home.py --sabotage
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

DEFAULT_PAGE = pathlib.Path.home() / "hirulab-tools" / "docs" / "take-home" / "index.html"

# ---- 国税庁の表(道具のコードを見ずに、公表されている表から書き下したもの) ----
# 給与所得控除(令和2年分以降)
SALARY_DEDUCTION = [
    (1_625_000, lambda x: min(x, 550_000)),
    (1_800_000, lambda x: x * 0.4 - 100_000),
    (3_600_000, lambda x: x * 0.3 + 80_000),
    (6_600_000, lambda x: x * 0.2 + 440_000),
    (8_500_000, lambda x: x * 0.1 + 1_100_000),
]
SALARY_DEDUCTION_MAX = 1_950_000

# 所得税の速算表(下限, 税率, 控除額)
BRACKETS = [
    (0, 0.05, 0),
    (1_950_000, 0.10, 97_500),
    (3_300_000, 0.20, 427_500),
    (6_950_000, 0.23, 636_000),
    (9_000_000, 0.33, 1_536_000),
    (18_000_000, 0.40, 2_796_000),
    (40_000_000, 0.45, 4_796_000),
]

DEFAULT_RATES = {
    "r_health": 5.00, "r_care": 0.80, "r_pension": 9.15, "r_emp": 0.55,
    "r_res": 10.0, "r_resflat": 5000, "d_basic": 480000, "d_basic_r": 430000,
    "d_dep": 380000, "d_dep_r": 330000, "r_recon": 2.1,
    "c_health_m": 1_390_000, "c_pension_m": 650_000,
    "c_health_b": 5_730_000, "c_pension_b": 1_500_000,
}


def salary_deduction(income):
    for cap, f in SALARY_DEDUCTION:
        if income <= cap:
            return f(income)
    return SALARY_DEDUCTION_MAX


def income_tax(taxable, brackets=None):
    if taxable <= 0:
        return 0.0
    rows = brackets or BRACKETS
    row = rows[0]
    for b in rows:
        if taxable >= b[0]:
            row = b
    return max(0.0, taxable * row[1] - row[2])


def model(annual, age, deps, rates, on, bonus=0, bonus_n=2, brackets=None):
    """画面に書いてある近似を、道具のコードを見ずに組み立て直したもの。

    ★2026-09-01: 社会保険料に上限が入った。月給ぶんと賞与ぶんを分け、
      健保は「月額の上限」と「賞与の年度累計の上限」、
      厚年は「月額の上限」と「賞与の1回あたりの上限」で頭打ちにする。
      雇用保険に上限は無い。
    """
    bonus = min(max(0, bonus), annual)
    bonus_n = max(1, round(bonus_n))
    monthly = max(0, annual - bonus) / 12
    per_bonus = bonus / bonus_n

    parts = {}
    if on["health"]:
        health_b = min(bonus, rates["c_health_b"])

        def health(r):
            return min(monthly, rates["c_health_m"]) * 12 * r / 100 + health_b * r / 100
        parts["health"] = health(rates["r_health"])
        if 40 <= age < 65:
            parts["care"] = health(rates["r_care"])
    if on["pension"]:
        r = rates["r_pension"]
        parts["pension"] = (min(monthly, rates["c_pension_m"]) * 12 * r / 100 +
                             min(per_bonus, rates["c_pension_b"]) * bonus_n * r / 100)
    if on["empIns"]:
        parts["emp"] = annual * rates["r_emp"] / 100
    si = sum(parts.values())

    sal_ded = salary_deduction(annual)
    after_sal = max(0.0, annual - sal_ded)

    ded_i = rates["d_basic"] + deps * rates["d_dep"] + si
    taxable_i = math.floor(max(0.0, after_sal - ded_i) / 1000) * 1000
    base_tax = income_tax(taxable_i, brackets)
    inc_tax = base_tax * (1 + rates["r_recon"] / 100)

    ded_r = rates["d_basic_r"] + deps * rates["d_dep_r"] + si
    taxable_r = math.floor(max(0.0, after_sal - ded_r) / 1000) * 1000
    res_tax = taxable_r * rates["r_res"] / 100 + rates["r_resflat"] if taxable_r > 0 else 0.0

    return {
        "parts": parts, "si": si, "salDed": sal_ded, "afterSal": after_sal,
        "taxableI": taxable_i, "baseTax": base_tax, "incTax": inc_tax,
        "taxableR": taxable_r, "resTax": res_tax,
        "net": annual - si - inc_tax - res_tax,
    }


# ============================ 画面を読む ============================

READ = """() => ({
  netY: document.querySelector('#netY').textContent,
  netM: document.querySelector('#netM').textContent,
  rate: document.querySelector('#rate').textContent,
  rows: Array.from(document.querySelectorAll('#tbody tr')).map(
    r => [r.dataset.k || ''].concat(Array.from(r.children).map(c => c.textContent.trim()))),
  detail: Array.from(document.querySelectorAll('#detail tr')).map(
    r => [r.dataset.k || ''].concat(Array.from(r.children).map(c => c.textContent.trim()))),
  bar: Array.from(document.querySelectorAll('#bar i')).map(e => e.style.width)
})"""


def yen(s):
    """"¥1,234" / "−¥1,234" → 数(円)。道具の表示と同じ丸め方で比べるために使う。"""
    neg = s.strip().startswith("−") or s.strip().startswith("-")
    m = re.search(r"[\d,]+", s)
    if not m:
        return None
    v = int(m.group(0).replace(",", ""))
    return -v if neg else v


def want_yen(v):
    """道具の yen() と同じ丸め。Math.round は .5 を +∞ 方向に上げる(Python の round と違う)。"""
    return math.floor(v + 0.5) if v >= 0 else -math.floor(-v + 0.5) if (-v) % 1 != 0.5 else -int(-v + 0.5)


def js_round(v):
    """JS の Math.round: 常に +∞ 方向に .5 を上げる。"""
    return math.floor(v + 0.5)


async def set_inputs(pg, annual, bonus, age, deps, rates, on, bonus_n=2):
    await pg.fill("#annual", str(annual))
    await pg.fill("#bonus", str(bonus))
    await pg.fill("#bonusN", str(bonus_n))
    await pg.fill("#age", str(age))
    await pg.fill("#deps", str(deps))
    for k, v in rates.items():
        await pg.fill("#" + k, str(v))
    for k in ("health", "pension", "empIns"):
        if await pg.is_checked("#" + k) != on[k]:
            await pg.click("#" + k)
    await pg.wait_for_timeout(15)


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


async def check_cases(pg, rep, cases):
    """本体。金額・内訳・途中経過・手取り率・棒の幅を全部読み戻す。"""
    bad, n = [], 0
    for annual, bonus, age, deps, rates, on, bonus_n in cases:
        await set_inputs(pg, annual, bonus, age, deps, rates, on, bonus_n)
        got = await pg.evaluate(READ)
        w = model(annual, age, deps, rates, on, bonus, bonus_n)
        tag = "年収%d 賞与%d×%d 齢%d 扶養%d %s" % (annual, bonus, bonus_n, age, deps,
                                                  "".join(k[0] for k in on if on[k]))
        n += 6 + len(w["parts"])

        if yen(got["netY"]) != js_round(w["net"]):
            bad.append("%s 手取り 道具=%s 参照=%d" % (tag, got["netY"], js_round(w["net"])))
        if yen(got["netM"]) != js_round(w["net"] / 12):
            bad.append("%s 月あたり 道具=%s 参照=%d" % (tag, got["netM"], js_round(w["net"] / 12)))
        want_rate = "%.1f%%" % (w["net"] / annual * 100) if annual else "—"
        if got["rate"] != want_rate:
            bad.append("%s 手取り率 道具=%s 参照=%s" % (tag, got["rate"], want_rate))

        # 内訳の表(額面 / 各保険 / 合計 / 所得税 / 住民税 / 手取り)
        # ★2026-09-02 夜: 行は**表示名ではなく `data-k`** で引く。表示名で引いていたので
        #   英語版に当てると 1 行も見つからず KeyError で落ちた(url・headers・jwt・date と同じ手)。
        rows = {r[0]: r for r in got["rows"]}
        for key, v in [("gross", annual), ("si-total", -w["si"]),
                       ("income-tax", -w["incTax"]), ("residence-tax", -w["resTax"]),
                       ("net", w["net"])]:
            if key not in rows:
                bad.append("%s 行が無い: %s" % (tag, key)); continue
            if yen(rows[key][2]) != js_round(abs(v)) * (1 if v >= 0 else -1):
                bad.append("%s %s 道具=%s 参照=%d" % (tag, key, rows[key][2], js_round(v)))
        for key, v in w["parts"].items():
            if key not in rows:
                bad.append("%s 保険の行が無い: %s" % (tag, key)); continue
            if yen(rows[key][2]) != -js_round(v):
                bad.append("%s %s 道具=%s 参照=%d" % (tag, key, rows[key][2], -js_round(v)))
        # 40歳未満/65歳以上に介護保険の行が出ていないこと
        if "care" in rows and not (40 <= age < 65 and on["health"]):
            bad.append("%s 介護保険の行が出ている(年齢 %d)" % (tag, age))

        # 途中経過
        det = {r[0]: r[2] for r in got["detail"]}
        for key, v in [("salary-deduction", w["salDed"]),
                       ("employment-income", w["afterSal"]),
                       ("taxable-income", w["taxableI"]),
                       ("base-tax", w["baseTax"]),
                       ("taxable-residence", w["taxableR"])]:
            if key not in det:
                bad.append("%s 途中経過の行が無い: %s" % (tag, key)); continue
            if yen(det[key]) != js_round(v):
                bad.append("%s %s 道具=%s 参照=%d" % (tag, key, det[key], js_round(v)))

        # 棒グラフの幅(手取り・社保・所得税・住民税の順)
        if annual:
            for i, v in enumerate([w["net"], w["si"], w["incTax"], w["resTax"]]):
                want = max(0.0, v) / annual * 100
                got_w = float(got["bar"][i].rstrip("%"))
                # ブラウザは style.width を有効数字6桁くらいに丸めて持つので、
                # ここは厳密には比べられない(49.404978% が "49.405%" になる)。
                if abs(got_w - want) > 1e-3:
                    bad.append("%s 棒[%d] 道具=%s 参照=%.6f%%" % (tag, i, got["bar"][i], want))
    rep.line("金額・内訳・途中経過・率・棒", n, bad)


async def check_bonus_matters(pg, rep):
    """★「うち賞与の合計」と「支給回数」が結果を動かすこと。

    9/1 昼まで、この欄は**結果を1円も変えなかった**(値を読んだあと1度も使っていなかった)。
    社会保険料の上限を入れて意味のある欄にしたので、**動くこと自体**を検査に固定する。
    上限を外すと動かなくなるので、この検査が落ちて気づける。
    """
    bad = []
    rates, on = dict(DEFAULT_RATES), {"health": True, "pension": True, "empIns": True}
    # 上限に当たる高い年収では、賞与の割り振りで手取りが変わる
    for annual in (20_000_000, 40_000_000):
        seen = set()
        for bonus in (0, annual // 4, annual // 2):
            await set_inputs(pg, annual, bonus, 30, 0, rates, on)
            seen.add((await pg.evaluate(READ))["netY"])
        if len(seen) == 1:
            bad.append("年収%d で賞与を変えても手取りが動かない: %s" % (annual, seen))
    # 厚年の賞与の上限は1回あたりなので、回数でも変わる
    seen = set()
    for n in (1, 2, 4):
        await set_inputs(pg, 20_000_000, 8_000_000, 30, 0, rates, on, n)
        seen.add((await pg.evaluate(READ))["netY"])
    if len(seen) != 3:
        bad.append("賞与の支給回数を変えても手取りが3通りにならない: %s" % sorted(seen))
    # ★上限に当たらない年収では、割り振っても変わらないのが正しい(効きすぎていないか)
    seen = set()
    for bonus in (0, 1_000_000, 2_000_000):
        await set_inputs(pg, 4_000_000, bonus, 30, 0, rates, on)
        seen.add((await pg.evaluate(READ))["netY"])
    if len(seen) != 1:
        bad.append("上限に当たらない年収400万で賞与により手取りが動いた: %s" % sorted(seen))
    rep.line("賞与の内訳と回数が効くこと(★9/1に直した件)", 4, bad)
    return not bad


async def check_rate_edit(pg, rep):
    """★看板機能: 料率を書き換えたら、書き換えた値で計算し直されること。"""
    bad, n = [], 0
    on = {"health": True, "pension": True, "empIns": True}
    edits = [
        ("r_health", 9.98), ("r_care", 1.60), ("r_pension", 0.0), ("r_emp", 1.10),
        ("r_res", 6.0), ("r_resflat", 12000), ("d_basic", 0), ("d_basic_r", 0),
        ("d_dep", 630000), ("d_dep_r", 450000), ("r_recon", 0.0),
        # 2026-09-01 に足した上限も、直せることを測る
        ("c_health_m", 300_000), ("c_pension_m", 200_000),
        ("c_health_b", 1_000_000), ("c_pension_b", 400_000),
    ]
    for key, val in edits:
        rates = dict(DEFAULT_RATES); rates[key] = val
        for annual, age, deps in [(4_000_000, 45, 1), (9_500_000, 30, 0),
                                  (24_000_000, 30, 0)]:
            bonus = annual // 4
            await set_inputs(pg, annual, bonus, age, deps, rates, on)
            got = await pg.evaluate(READ)
            w = model(annual, age, deps, rates, on, bonus, 2)
            n += 1
            if yen(got["netY"]) != js_round(w["net"]):
                bad.append("%s=%s 年収%d 道具=%s 参照=%d"
                           % (key, val, annual, got["netY"], js_round(w["net"])))
    rep.line("料率を書き換えたときの再計算(看板機能)", n, bad)


async def check_bracket_edit(pg, rep):
    """税率表を書き換えたら、それで計算し直されること + 初期値に戻せること。"""
    bad = []
    on = {"health": True, "pension": True, "empIns": True}
    await set_inputs(pg, 9_500_000, 0, 30, 0, dict(DEFAULT_RATES), on)
    # 全部 0% にすると、所得税だけが 0 になるはず
    cells = await pg.query_selector_all('#brackets input[data-j="1"]')
    for c in cells:
        await c.fill("0")
    await pg.wait_for_timeout(30)
    got = await pg.evaluate(READ)
    det = {r[0]: r[2] for r in got["detail"]}
    if yen(det["base-tax"]) != 0:
        bad.append("税率を全部0%%にしても所得税が残る: %s" % det["base-tax"])
    zero = dict(DEFAULT_RATES)
    w = model(9_500_000, 30, 0, zero, on, 0, 2, [(b[0], 0.0, b[2]) for b in BRACKETS])
    if yen(got["netY"]) != js_round(w["net"]):
        bad.append("税率0%%のときの手取り 道具=%s 参照=%d" % (got["netY"], js_round(w["net"])))
    await pg.click("#resetBr")
    await pg.wait_for_timeout(30)
    got = await pg.evaluate(READ)
    w = model(9_500_000, 30, 0, zero, on)
    if yen(got["netY"]) != js_round(w["net"]):
        bad.append("税率表を戻したのに元に戻らない 道具=%s 参照=%d" % (got["netY"], js_round(w["net"])))
    rep.line("税率表の書き換えと初期化", 3, bad)


async def check_persist(pg, rep, url):
    """料率がこの端末に保存されて、読み直しても残ること(画面がそう書いている)。"""
    bad = []
    rates = dict(DEFAULT_RATES); rates["r_health"] = 7.77
    on = {"health": True, "pension": True, "empIns": True}
    await set_inputs(pg, 4_000_000, 0, 30, 0, rates, on)
    await pg.goto(url)
    await pg.wait_for_timeout(60)
    v = await pg.eval_on_selector("#r_health", "e => e.value")
    if float(v) != 7.77:
        bad.append("読み直したら健康保険料率が %s に戻った(保存されていない)" % v)
    await pg.click("#reset")
    await pg.wait_for_timeout(30)
    v = await pg.eval_on_selector("#r_health", "e => e.value")
    if float(v) != DEFAULT_RATES["r_health"]:
        bad.append("「初期値に戻す」で戻らない: %s" % v)
    rep.line("料率がこの端末に残ること", 2, bad)


# ============================ 見本 ============================

def make_cases(rng, n):
    on_all = {"health": True, "pension": True, "empIns": True}
    R = DEFAULT_RATES

    def case(annual, bonus=0, age=30, deps=0, on=None, bn=2, rates=None):
        return (annual, bonus, age, deps, dict(rates or R), dict(on or on_all), bn)

    cases = []
    for _ in range(n):
        annual = rng.choice([rng.randrange(0, 3_000_000, 10_000),
                             rng.randrange(3_000_000, 12_000_000, 10_000),
                             rng.randrange(12_000_000, 60_000_000, 100_000)])
        bonus = rng.choice([0, 0, annual // rng.randint(3, 10), annual // 2])
        on = {k: rng.random() < 0.8 for k in ("health", "pension", "empIns")}
        cases.append(case(annual, bonus, rng.randint(15, 99), rng.randint(0, 10),
                          on, rng.randint(1, 12)))

    # ★「薄い領域」対策。ランダムでは境目にまず当たらないので手で置く。
    for e in (1_625_000, 1_800_000, 3_600_000, 6_600_000, 8_500_000):   # 給与所得控除の折れ点
        for d in (-1000, 0, 1000):
            cases.append(case(e + d))
    # 課税所得が速算表の境目ちょうどになる年収を総当たりで探す
    for target in (1_950_000, 3_300_000, 6_950_000, 9_000_000, 18_000_000, 40_000_000):
        annual, best = None, None
        for a in range(1_000_000, 70_000_000, 1000):
            tx = model(a, 30, 0, R, on_all)["taxableI"]
            if tx == target:
                annual = a; break
            if tx > target:
                best = a; break
        for a in (annual, best):
            if a:
                cases += [case(a - 1000), case(a), case(a + 1000)]
    for age in (39, 40, 64, 65):                                        # 介護保険の境目
        cases.append(case(5_000_000, age=age))
    # ★社会保険料の上限の境目(2026-09-01 に入れたところ)
    for cap, name in ((R["c_pension_m"], "厚年の月額"), (R["c_health_m"], "健保の月額")):
        for d in (-12_000, 0, 12_000):
            cases.append(case(cap * 12 + d))                            # 月給だけで上限をまたぐ
    for d in (-10_000, 0, 10_000):
        cases.append(case(30_000_000, bonus=R["c_health_b"] + d))       # 健保の賞与の年度累計
        cases.append(case(30_000_000, bonus=(R["c_pension_b"] + d) * 2, bn=2))  # 厚年の1回あたり
    cases += [
        case(0),                                                        # 年収0
        case(550_000),                                                  # 給与所得控除 = 収入
        case(1_030_000),                                                # いわゆる103万
        case(5_000_000, deps=10),                                       # 扶養が多くて課税所得0
        case(4_000_000, on={"health": False, "pension": False, "empIns": False}),
        case(6_000_000, bonus=6_000_000),                               # 全部が賞与
        case(6_000_000, bonus=6_000_000, bn=12),                        # 全部が賞与・12回
        case(6_000_000, bonus=0, bn=1),
    ]
    return cases


SABOTAGE = [
    ("給与所得控除の上限を外す",
     ('  return 1950000;', '  return income*0.1 + 1100000;')),
    ("給与所得控除の最低額の頭打ちを外す",
     ('  if (income <= 1625000) return Math.min(income, 550000);',
      '  if (income <= 1625000) return 550000;')),
    ("課税所得の千円未満切り捨てをやめる",
     ('  const taxableI = Math.floor(Math.max(0, incomeAfterSal - dedI) / 1000) * 1000;',
      '  const taxableI = Math.max(0, incomeAfterSal - dedI);')),
    ("速算表の控除額を引かない",
     ('  return Math.max(0, taxable * (row[1]/100) - row[2]);',
      '  return Math.max(0, taxable * (row[1]/100));')),
    ("復興特別所得税を掛けない",
     ('  const incTax = baseTax * (1 + R.r_recon/100);', '  const incTax = baseTax;')),
    ("住民税の均等割を、課税所得0でも足す",
     ('  const resTax = taxableR > 0 ? taxableR * R.r_res/100 + R.r_resflat : 0;',
      '  const resTax = taxableR * R.r_res/100 + R.r_resflat;')),
    ("社会保険料を所得控除に入れない",
     ('  const dedI = R.d_basic + deps*R.d_dep + si;',
      '  const dedI = R.d_basic + deps*R.d_dep;')),
    ("介護保険の上の年齢を見ない",
     ('    if (age >= 40 && age < 65) parts.push(["care", "介護保険", health(R.r_care)]);',
      '    if (age >= 40) parts.push(["care", "介護保険", health(R.r_care)]);')),
    ("住民税の扶養控除を所得税のほうの額で引く",
     ('  const dedR = R.d_basic_r + deps*R.d_dep_r + si;',
      '  const dedR = R.d_basic_r + deps*R.d_dep + si;')),
    # ---- 2026-09-01 に入れた上限まわり ----
    ("厚生年金の月額の上限を見ない(9/1に直した傷そのもの)",
     ('    Math.min(monthlyPay, capM) * 12 * rate/100 +',
      '    monthlyPay * 12 * rate/100 +')),
    ("厚生年金の賞与の上限を見ない",
     ('    Math.min(perBonus, capB) * bonusN * rate/100;',
      '    perBonus * bonusN * rate/100;')),
    ("健保の賞与の上限を「1回あたり」と取り違える",
     ('    const healthB = Math.min(bonus, R.c_health_b);',
      '    const healthB = Math.min(perBonus, R.c_health_b) * bonusN;')),
    ("健保の月額の上限を厚年の上限と取り違える",
     ('    const health = r => Math.min(monthlyPay, R.c_health_m) * 12 * r/100 + healthB * r/100;',
      '    const health = r => Math.min(monthlyPay, R.c_pension_m) * 12 * r/100 + healthB * r/100;')),
    ("月給ぶんから賞与を引かない(賞与を二重に数える)",
     ('  const monthlyPay = Math.max(0, annual - bonus) / 12;',
      '  const monthlyPay = annual / 12;')),
    ("賞与の支給回数を読まず、いつも2回とする",
     ('  const bonusN = Math.max(1, Math.round(+$("#bonusN").value || 1));',
      '  const bonusN = 2;')),
    ("雇用保険にも厚年の上限を掛ける",
     ('  if ($("#empIns").checked)  parts.push(["emp", "雇用保険", annual * R.r_emp/100]);',
      '  if ($("#empIns").checked)  parts.push(["emp", "雇用保険", si2(R.r_emp, R.c_pension_m, R.c_pension_b)]);')),
    ("料率の書き換えを読まず、初期値を使う",
     ('  for (const k in DEFAULT_RATES) R[k] = parseFloat($("#"+k).value) || 0;',
      '  for (const k in DEFAULT_RATES) R[k] = DEFAULT_RATES[k];')),
    ("棒グラフの幅を額面でなく手取りで割る",
     ('    `<i style="width:${Math.max(0,v)/annual*100}%;background:${c}"></i>`).join("") : "";',
      '    `<i style="width:${Math.max(0,v)/net*100}%;background:${c}"></i>`).join("") : "";')),
]


async def run(html_path, n, seed, quiet=False):
    rng = random.Random(seed)
    cases = make_cases(rng, n)
    rep = Report()
    url = pathlib.Path(html_path).resolve().as_uri()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context()
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(url)
        await check_cases(pg, rep, cases)
        matters = await check_bonus_matters(pg, rep)
        await check_rate_edit(pg, rep)
        await check_bracket_edit(pg, rep)
        await check_persist(pg, rep, url)
        if errs:
            rep.line("JSエラー", 0, errs)
        await b.close()
    if not quiet:
        rep.show()
        if matters:
            print("\n★「うち賞与の合計」と「支給回数」が結果を動かすことを確認"
                  "(9/1 昼まではどちらも1円も動かさなかった)。")
    return rep


async def sabotage(html_path, n, seed):
    src = pathlib.Path(html_path).read_text(encoding="utf-8")
    tmp = pathlib.Path(html_path).with_name("_sabotage_take_home.html")
    print("わざと壊して、検査が捕まえるか見る(%d 種)\n" % len(SABOTAGE))
    missed = []
    try:
        for i, (name, (a, b)) in enumerate(SABOTAGE, 1):
            if a not in src:
                print("%2d. %-44s ★仕込めない(差し替え元が見つからない)" % (i, name))
                missed.append(name); continue
            tmp.write_text(src.replace(a, b, 1), encoding="utf-8", newline="\n")
            rep = await run(tmp, max(30, n // 4), seed + i, quiet=True)
            if rep.ok():
                print("%2d. %-44s ★素通り" % (i, name)); missed.append(name)
            else:
                print("%2d. %-44s 検出(%s)" % (i, name, sorted({x for x, _ in rep.bad})[0]))
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
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--sabotage", action="store_true")
    args = ap.parse_args()
    if args.sabotage:
        return asyncio.run(sabotage(args.page, args.n, args.seed))
    rep = asyncio.run(run(args.page, args.n, args.seed))
    return 0 if rep.ok() else 1


if __name__ == "__main__":
    sys.exit(main())
