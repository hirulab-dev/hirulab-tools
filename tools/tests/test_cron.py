#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cron式の読み下しツールの検証。

ページ内の JS コア（/*==CORE-START==*/ 〜 /*==CORE-END==*/）を Chromium に読ませ、
Python の croniter と「次の実行時刻」を突き合わせる。

    python tools/tests/test_cron.py docs/cron/index.html [--n 3000] [--seed 42]

croniter との既知の解釈差はコード中の SKIP_* に理由つきで書いてある。
"""
import argparse
import datetime as dt
import random
import re
import sys

from croniter import croniter, CroniterBadCronError
from playwright.sync_api import sync_playwright

CORE_RE = re.compile(r"/\*==CORE-START==\*/(.*?)/\*==CORE-END==\*/", re.S)

# croniter の day_or=True(既定)が Vixie cron と同じ「日 or 曜日」規則にあたる。
CRONITER_KW = dict(day_or=True)

# ---------------------------------------------------------------------------
# croniter との既知の解釈差（どちらが正しいかを調べたうえでの意図的なズレ）
#
# D1: 「n-n」のような幅ゼロの範囲。
#     croniter は "Jan-Jan, or Sun-Sun ... means the whole cycle" というコメント付きで
#     全体（そのフィールドの全値）に展開する（croniter.py の `elif low == high:`）。
#     Vixie cron の get_range() は num1..num2 をそのまま回すだけなので「n だけ」になる。
#     このツールは Vixie に合わせている。
#
# D2: 日・曜日フィールドが「*/n」のときの OR 判定。
#     Vixie cron は load_entry() でフィールドの **先頭の1文字** が '*' かどうかを見て
#     DOM_STAR / DOW_STAR を立てる。つまり「*/2」も「絞っていない」側に入り、
#     もう片方だけを見る（AND 側の挙動になる）。
#     croniter は展開後の値で絞りの有無を見るので「*/2」を絞りとみなし OR にする。
#     このツールは Vixie に合わせている。
#
# D3: 日にちがその月に存在せず、かつ曜日が絞られている式（例: 0 0 31 2 1）。
#     OR 規則なので「2月の月曜」が該当する。croniter 自身も OR を実装している
#     （0 0 31 1 1 は1月の月曜を返す）のに、日にちが月に存在しない場合だけ
#     CroniterBadDateError("failed to find next date") を投げて探索を諦める。
#     これは意図的な設計ではなく取りこぼしに見える。このツールは月曜を返す。
#
# 検証では (a) この3点を踏まえてランダム生成を作り分け、(b) 差が実際に出ることを
# 専用のケースで確かめる、の両方をやる。差を黙って避けるのはごまかしになるため。
# ---------------------------------------------------------------------------

DIVERGENCES = [
    # (式, 基準時刻, 理由)
    ("0 0 * * 5-5", dt.datetime(2027, 4, 1), "D1: 5-5 を croniter は全曜日に展開する"),
    ("5-5 0 * * *", dt.datetime(2027, 4, 1), "D1: 分の 5-5 も全分に展開される"),
    ("0 0 * 3-3 *", dt.datetime(2027, 4, 1), "D1: 月の 3-3 も全月に展開される"),
    ("0 0 6 * */12", dt.datetime(2027, 4, 1), "D2: 曜日 */12 を Vixie は星、croniter は絞りとみなす"),
    ("0 0 */10 * 3", dt.datetime(2027, 4, 1), "D2: 日 */10 を Vixie は星、croniter は絞りとみなす"),
    ("0 0 31 2 1", dt.datetime(2026, 1, 1), "D3: 2月31日は無いが2月の月曜はある。croniter は諦める"),
    ("0 0 31 4 5", dt.datetime(2026, 1, 1), "D3: 4月31日は無いが4月の金曜はある。croniter は諦める"),
]


def gen_field(rng, lo, hi, names=None, allow_star_step=True):
    """ランダムな1フィールドを作る。幅ゼロの範囲(D1)は作らない。"""
    kind = rng.random()
    if kind < 0.30:
        return "*"
    if kind < 0.45 and allow_star_step:
        step = rng.choice([2, 3, 4, 5, 6, 7, 10, 12, 15, 20, 30])
        return "*/%d" % step
    if kind < 0.60 and hi > lo:
        a = rng.randint(lo, hi - 1)
        b = rng.randint(a + 1, hi)
        return "%d-%d" % (a, b)
    if kind < 0.72 and hi > lo:
        a = rng.randint(lo, hi - 1)
        b = rng.randint(a + 1, hi)
        step = rng.randint(2, 6)
        return "%d-%d/%d" % (a, b, step)
    if kind < 0.85:
        n = rng.randint(1, 4)
        vals = sorted({rng.randint(lo, hi) for _ in range(n)})
        return ",".join(str(v) for v in vals)
    if names and kind < 0.93:
        return rng.choice(names)
    return str(rng.randint(lo, hi))


MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
DOWS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]


def gen_expr(rng):
    # 日と曜日は「*/n」を出さない(D2)。片方でも */n が出ると OR 判定の解釈差に当たる。
    return " ".join([
        gen_field(rng, 0, 59),
        gen_field(rng, 0, 23),
        gen_field(rng, 1, 31, allow_star_step=False),
        gen_field(rng, 1, 12, MONTHS),
        gen_field(rng, 0, 6, DOWS, allow_star_step=False),
    ])


FIXED = [
    "* * * * *", "0 9 * * 1-5", "*/15 * * * *", "*/7 * * * *",
    "0 0 1 * *", "30 3 1 * 1", "0 0 29 2 *", "0 */2 * * SAT,SUN",
    "15 10 * * *", "0 0 31 * *", "59 23 31 12 *", "0 0 * * 7",
    "0 0 * * 0-7", "5/10 * * * *", "0 9-17/2 * * MON-FRI",
    "@daily", "@weekly", "@monthly", "@yearly", "@hourly",
    "0 0 1-7 * 1", "1,2,3 4,5 6,7 8,9 0,6", "0 12 1 JAN-MAR MON",
]

ALIASES = {
    "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


def js_next_n(page, expr, base_iso, n):
    return page.evaluate(
        """([expr, baseIso, n]) => {
             try {
               const cron = parseCron(expr);
               const [d, t] = baseIso.split('T');
               const [Y, Mo, D] = d.split('-').map(Number);
               const [H, Mi, S] = t.split(':').map(Number);
               const start = Date.UTC(Y, Mo - 1, D, H, Mi, S) + 60000; // 基準時刻の次から
               const outs = nextN(cron, start, n);
               return { ok: true, runs: outs.map(w => {
                 const x = new Date(w);
                 const p = k => String(k).padStart(2, '0');
                 return x.getUTCFullYear() + '-' + p(x.getUTCMonth()+1) + '-' + p(x.getUTCDate())
                      + 'T' + p(x.getUTCHours()) + ':' + p(x.getUTCMinutes()) + ':' + p(x.getUTCSeconds());
               })};
             } catch (e) { return { ok: false, err: String(e.message || e) }; }
           }""",
        [expr, base_iso, n],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=20260822)
    ap.add_argument("--runs", type=int, default=6)
    args = ap.parse_args()

    src = open(args.html, encoding="utf-8").read()
    m = CORE_RE.search(src)
    if not m:
        print("CORE マーカーが見つかりません")
        return 2
    core = m.group(1)
    print("core: %d 文字" % len(core))

    rng = random.Random(args.seed)
    exprs = list(FIXED)
    while len(exprs) < args.n:
        exprs.append(gen_expr(rng))

    bases = [
        dt.datetime(2026, 8, 22, 9, 0, 0),
        dt.datetime(2027, 2, 28, 23, 59, 0),
        dt.datetime(2028, 2, 29, 12, 0, 0),   # うるう年
        dt.datetime(2026, 12, 31, 23, 30, 0),
        dt.datetime(2026, 1, 1, 0, 0, 0),
    ]

    ok = mismatch = skipped = cmp_count = 0
    bad = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_content("<!doctype html><meta charset=utf-8>")
        page.add_script_tag(content=core)

        for i, expr in enumerate(exprs):
            base = bases[i % len(bases)]
            expanded = ALIASES.get(expr.lower(), expr)
            try:
                it = croniter(expanded, base, **CRONITER_KW)
                expected = [it.get_next(dt.datetime).strftime("%Y-%m-%dT%H:%M:%S")
                            for _ in range(args.runs)]
            except (CroniterBadCronError, ValueError, KeyError):
                skipped += 1
                continue

            got = js_next_n(page, expr, base.strftime("%Y-%m-%dT%H:%M:%S"), args.runs)
            if not got["ok"]:
                mismatch += 1
                bad.append((expr, base, "JS エラー: " + got["err"], expected))
                continue
            cmp_count += len(expected)
            if got["runs"] == expected:
                ok += 1
            else:
                mismatch += 1
                if len(bad) < 20:
                    bad.append((expr, base, got["runs"], expected))

        # --- 既知の解釈差が「実際に差として出ること」を確かめる ---
        print("\n--- 既知の解釈差（意図的。Vixie cron に合わせている） ---")
        div_ok = 0
        for expr, base, why in DIVERGENCES:
            try:
                it = croniter(expr, base, **CRONITER_KW)
                exp = [it.get_next(dt.datetime).strftime("%Y-%m-%dT%H:%M:%S")
                       for _ in range(args.runs)]
            except Exception as err:            # D3 はここに落ちる
                exp = ["<croniter エラー: %s>" % type(err).__name__]
            got = js_next_n(page, expr, base.strftime("%Y-%m-%dT%H:%M:%S"), args.runs)
            differs = (not got["ok"]) or got["runs"] != exp
            print("%-16s %s  → %s" % (expr, "差あり(想定どおり)" if differs else "差なし(!!)", why))
            if differs:
                div_ok += 1
            else:
                bad.append((expr, base, "差が出るはずが出なかった", exp))
        print("差が想定どおり出た: %d / %d" % (div_ok, len(DIVERGENCES)))

        browser.close()

    print("\n照合した式: %d / 一致: %d / 不一致: %d / croniter が読めず飛ばした: %d"
          % (ok + mismatch, ok, mismatch, skipped))
    print("照合した時刻の数: %d" % cmp_count)
    if bad:
        print("\n--- 不一致の例 ---")
        for expr, base, got, exp in bad[:20]:
            print("式: %-32s 基準: %s" % (expr, base))
            print("   こちら : %s" % (got if isinstance(got, str) else got[:3]))
            print("   croniter: %s" % exp[:3])
    return 1 if (mismatch or div_ok != len(DIVERGENCES)) else 0


if __name__ == "__main__":
    sys.exit(main())
