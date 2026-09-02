#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日付計算機( docs/date/ )を、出どころの違う参照と突き合わせる。2026-09-01 昼に新設。

★**2026-08-15 公開の道具なのに、検証が1本も無かった**(page-contrast / diff / json / unit /
  char-counter / contrast / palette に続いて8本目。古い道具ほど薄い、を後ろから埋めている)。

## 参照を出どころで分ける(1つの参照に全部を当てない)

| 見るもの | 参照 | どこから来たか |
|---|---|---|
| 日本の祝日(1949〜2099) | **jpholiday** | 第三者のライブラリ |
| 営業日・土日・平日の祝日の数 | **numpy.busday_count** | 第三者。休日一覧は jpholiday から渡す |
| 年月日の内訳・月/年の加減算 | **dateutil.relativedelta** | 第三者 |
| 日数・週・曜日・通算日 | **Python 標準の datetime** | 標準ライブラリ |
| 和暦・年度・学年 | このファイルに独立に書いた表と式 | 法令・学校教育法から書き下し |
| 画面の表示 | 実際に描かれたカードを読み戻す | 道具自身 |

## ★この検証で見つけたこと(2026-09-01)

**祝日の規則が「いまの規則」だけで、1949〜2021年の73年ぶんが黙って間違っていた。**
画面は1949年から受け付けるので、利用者には正しそうな一覧が出る。しかも祝日は
**期間タブの「営業日」の数にも効く**ので、間違いは日数計算にも回っていた。
(成人の日は1999年まで1月15日 / 天皇誕生日は平成のあいだ12月23日 / 海の日は1995年まで無い /
 体育の日は1999年まで10月10日 / 2020・2021年は五輪で3つ動いた / 一日限りの休日が6つある)
あわせて**春分・秋分の近似式が1980年より前は定数が違う**のに片方しか使っていなかった。

## ★参照(jpholiday)のほうが法律と違うところが2つある

どちらも jpholiday が**規則を過去にさかのぼって当てている**。道具は法律どおりにした。
- **国民の休日**は昭和60年法律第103号(1985-12-27 施行)なので最初は 1986-05-04。
  jpholiday は 1949年からの5月4日を全部そう呼ぶ(31日ぶん)
- **振替休日**は昭和48年法律第10号(1973-04-12 施行)なので最初は 1973-04-30。
  jpholiday は同じ年の 1973-02-12 も振替休日にする
**この2つの差が「出ること自体」を検査している**(黙って合わせない)。ほかに差は無い。
名前の綴りも3つだけ違う(jpholiday 側に中黒の重複がある)ので、それも明示して許す。

## ★2026-09-02 昼: 英語版にも同じ検査を当てられるようにした

英語版( `docs/en/date.html` )は日本語版から生成していて、**文字列の中身を空にすると
コードがバイト単位で一致する**。だから計算そのものは同じはずだが、
**訳したせいで画面が壊れていないか**はページを読まないと分からない。

そのために2つ変えた。
1. **カードを `data-k`(言葉でない名札)で引く**。前はラベルの文字(「満年齢」)で引いていたので、
   英語版にはそのままでは当たらなかった(url/headers/jwt の `data-code` と同じ手)。
2. **言葉の比較を言語パック(`LANGS`)に分けた**。数・ISO形式・日付の並びは言葉を読まないので
   両方に当たる。祝日の名前と元号の英語表記は**この表に独立に書いてある**
   (生成器の訳表を import すると、訳が間違っていても気づけないため。**わざと2か所に書いている**)。

使い方:
    python lab/scripts/test_date.py                       # 手元のページ
    python lab/scripts/test_date.py --page <html>          # 本番から落としたHTMLに当てる
    python lab/scripts/test_date.py --lang en              # 英語版に当てる(既定は ja)
    python lab/scripts/test_date.py --n 300                # 見本の数(既定 300)
    python lab/scripts/test_date.py --sabotage             # わざと壊して、検査が捕まえるか見る
"""
import argparse
import asyncio
import datetime as dt
import pathlib
import random
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

import jpholiday                                  # noqa: E402  第三者(祝日)
import numpy as np                                # noqa: E402  第三者(営業日)
from dateutil.relativedelta import relativedelta  # noqa: E402  第三者(月・年の加減算)
from playwright.async_api import async_playwright  # noqa: E402

D = dt.date
# 曜日・月の名前は言語パック(LANGS)に持たせる。ここでは持たない

DEFAULT_PAGE = pathlib.Path.home() / "hirulab-tools" / "docs" / "date" / "index.html"
EN_PAGE = pathlib.Path.home() / "hirulab-tools" / "docs" / "en" / "date.html"

MON_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WD_EN = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]      # 道具の表示の順

# ---- 言語ごとに違うのは「言葉」だけ。数・ISO形式・並びはどちらでも同じ ----
#
# ⚠ 祝日の名前と元号の英語表記は **生成器(make_en_date.py)から import しない**。
#    同じ表を見に行くと「訳が間違っていても一致する」ので、検査の意味が消える。
#    ここは内閣府の英語表記から独立に書いた**2つ目の写し**で、食い違えば落ちる。
HOLIDAY_EN = {
    "元日": "New Year's Day",
    "成人の日": "Coming of Age Day",
    "建国記念の日": "National Foundation Day",
    "天皇誕生日": "The Emperor's Birthday",
    "春分の日": "Vernal Equinox Day",
    "みどりの日": "Greenery Day",
    "昭和の日": "Showa Day",
    "憲法記念日": "Constitution Memorial Day",
    "こどもの日": "Children's Day",
    "海の日": "Marine Day",
    "山の日": "Mountain Day",
    "敬老の日": "Respect for the Aged Day",
    "秋分の日": "Autumnal Equinox Day",
    "スポーツの日": "Sports Day",
    "体育の日": "Health and Sports Day",
    "文化の日": "Culture Day",
    "勤労感謝の日": "Labor Thanksgiving Day",
    "振替休日": "Substitute holiday",
    "国民の休日": "Citizens' holiday",
    "皇太子明仁親王の結婚の儀": "Wedding of Crown Prince Akihito",
    "昭和天皇の大喪の礼": "Funeral of Emperor Showa",
    "即位礼正殿の儀": "Enthronement Ceremony at the Seiden",
    "皇太子徳仁親王の結婚の儀": "Wedding of Crown Prince Naruhito",
    "天皇の即位の日": "Enthronement Day of the Emperor",
}
ERA_EN = {"令和": "Reiwa", "平成": "Heisei", "昭和": "Showa", "大正": "Taisho", "明治": "Meiji"}


def _grade_ja(g):
    return (("年長(小学校入学の前年度)" if g == 0 else "小学校入学まであと%d年度" % (1 - g))
            if g < 1 else
            "小学%d年生" % g if g <= 6 else
            "中学%d年生" % (g - 6) if g <= 9 else
            "高校%d年生" % (g - 9) if g <= 12 else
            "大学%d年生相当" % (g - 12) if g <= 16 else
            "高校卒業から%d年度目" % (g - 12))


def _grade_en(g):
    return (("Final nursery year (the year before school starts)" if g == 0 else
             "%d school years before elementary school" % (1 - g))
            if g < 1 else
            "Elementary school, year %d" % g if g <= 6 else
            "Junior high school, year %d" % (g - 6) if g <= 9 else
            "High school, year %d" % (g - 9) if g <= 12 else
            "University, year %d (equivalent)" % (g - 12) if g <= 16 else
            "%d school years since high school" % (g - 12))


LANGS = {
    "ja": {
        "wd": ["日", "月", "火", "水", "木", "金", "土"],
        "fmt": lambda d, L: "%d年%d月%d日(%s)" % (d.year, d.month, d.day,
                                                  L["wd"][(d.weekday() + 1) % 7]),
        "ymd": lambda y, m, dd: "%d年%dか月%d日" % (y, m, dd),
        "wareki": lambda era, n, m, dd: "%s%s年%d月%d日" % (era, "元" if n == 1 else n, m, dd),
        "era": lambda ja: ja,
        "dow": lambda d, L: L["wd"][(d.weekday() + 1) % 7] + "曜日",
        "fiscal": lambda y: "%d年度" % y,
        "grade": _grade_ja,
        "hol_name": lambda ja: ja,
        "hol_date": lambda d: "%d月%d日" % (d.month, d.day),
        "summary": r"計 (\d+) 日 .* (\d+) 日",
        "errs": ["開始", "開始", "入って", "存在"],
    },
    "en": {
        "wd": WD_EN,
        "fmt": lambda d, L: "%d %s %d (%s)" % (d.year, MON_EN[d.month - 1], d.day,
                                               L["wd"][(d.weekday() + 1) % 7]),
        "ymd": lambda y, m, dd: "%dy %dm %dd" % (y, m, dd),
        "wareki": lambda era, n, m, dd: "%s %d, %s %d" % (era, n, MON_EN[m - 1], dd),
        "era": lambda ja: ERA_EN[ja],
        "dow": lambda d, L: L["wd"][(d.weekday() + 1) % 7],
        "fiscal": lambda y: "FY%d" % y,
        "grade": _grade_en,
        "hol_name": lambda ja: HOLIDAY_EN[ja],
        "hol_date": lambda d: "%s %d" % (MON_EN[d.month - 1], d.day),
        "summary": r"(\d+) holidays in total — (\d+) of them",
        "errs": ["is before", "is before", "falls inside", "No such date"],
    },
}

# ---- 参照(jpholiday)と法律の食い違い。ここに書いたものだけを許す ----
NAME_VARIANTS = {                                  # jpholiday 側の綴り: 法令の名称
    "皇太子・明仁親王の結婚の儀": "皇太子明仁親王の結婚の儀",
    "即位の礼正殿の儀": "即位礼正殿の儀",
    "皇太子・皇太子徳仁親王の結婚の儀": "皇太子徳仁親王の結婚の儀",
}
SUBSTITUTE_LAW_FROM = D(1973, 4, 12)               # 振替休日の施行日
NATIONAL_LAW_FROM = D(1986, 1, 1)                  # 国民の休日が最初に効いた年

# ---- 和暦(独立に書いた表) ----
ERAS = [("令和", D(2019, 5, 1)), ("平成", D(1989, 1, 8)), ("昭和", D(1926, 12, 25)),
        ("大正", D(1912, 7, 30)), ("明治", D(1868, 1, 25))]


def wareki_parts(d):
    """(元号の日本語名, 何年目)。見せ方は言語パックに任せる。"""
    for name, start in ERAS:
        if d >= start:
            return name, d.year - start.year + 1
    return None


def to_wareki(d, L):
    p = wareki_parts(d)
    return None if not p else L["wareki"](L["era"](p[0]), p[1], d.month, d.day)


def school_grade(birth, at):
    """学年(日本の年度)。4月2日〜翌4月1日が同じ学年、という決まりから独立に書く。"""
    base = birth.year - 1 if (birth.month < 4 or (birth.month == 4 and birth.day == 1)) else birth.year
    fiscal = at.year - 1 if at.month < 4 else at.year
    return fiscal - base - 5, fiscal


def ref_holidays(y):
    """jpholiday の一覧を、名前の綴りだけ法令の側に寄せて返す。"""
    out = {}
    for d, name in jpholiday.year_holidays(y):
        if name.endswith(" 振替休日"):
            name = "振替休日"
        out[d] = NAME_VARIANTS.get(name, name)
    return out


def ref_holidays_by_law(y):
    """jpholiday から、法律の施行日より前に当てはめられた分を落としたもの。

    ここで落とすのは **2種類だけ**。落とした件数は呼び出し側で数えて表に出す。
    """
    out, dropped = {}, []
    for d, name in ref_holidays(y).items():
        if name == "国民の休日" and d < NATIONAL_LAW_FROM:
            dropped.append((d, name)); continue
        if name == "振替休日" and d < SUBSTITUTE_LAW_FROM:
            dropped.append((d, name)); continue
        out[d] = name
    return out, dropped


# ============================ 道具を読む ============================

# ★カードは `data-k` で引く(ラベルの文字で引くと英語版に当たらない。2026-09-02)
READ_CARDS = """sel => Array.from(document.querySelectorAll(sel + ' .card')).map(c => ({
  k: c.dataset.k || '',
  label: c.querySelector('.label').textContent.trim(),
  value: c.querySelector('.value').textContent.trim(),
  note: (c.querySelector('.note') || { textContent: '' }).textContent.trim()
}))"""

READ_HOLIDAYS = """y => { const m = holidays(y); const o = {};
  Object.keys(m).forEach(k => { k = +k;
    o[String(Math.floor(k/10000)).padStart(4,'0') + '-' +
      String(Math.floor(k/100)%100).padStart(2,'0') + '-' +
      String(k%100).padStart(2,'0')] = m[k]; });
  return o; }"""


def cards_to_map(cards):
    """名札(`data-k`)でカードを引けるようにする。

    ★名札が空のカードがあったら、それ自体を食い違いとして見えるようにする
      (`data-k` を落とすと、カードが出ていない扱いになって検査に掛かる)。
    """
    return {c["k"]: c for c in cards if c["k"]}


def missing(c, labels):
    """出るはずのカードが出ていないこと自体を食い違いとして扱う。

    ★壊すと例外で落ちてカードが1枚も出ない、という壊れ方がある。
      素の辞書引きだと検査のほうが KeyError で死んで「捕まえた」ではなくなるので、
      ここで受け止めて食い違いとして数える(`--sabotage` の 8番目で実際に踏んだ)。
    """
    return [l for l in labels if l not in c]


def num_of(s):
    """"1,234日" → 1234 / "12.3週" → 12.3"""
    m = re.search(r"-?[\d,]+(?:\.\d+)?", s)
    return None if not m else float(m.group(0).replace(",", ""))


async def set_date(pg, sel, d):
    await pg.fill(sel, d.isoformat())


# ============================ 検査の本体 ============================

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


async def check_holidays(pg, rep, L):
    """1949〜2099年の祝日を jpholiday と突き合わせる。

    ★英語版では、名前は `HOLIDAY_EN`(この検査に独立に書いた表)を通して比べる。
      道具の訳表とは別の写しなので、綴りが食い違えばここで落ちる。
    """
    bad, n, dropped_total = [], 0, 0
    for y in range(1949, 2100):
        got_raw = await pg.evaluate(READ_HOLIDAYS, y)
        got = {D(*map(int, k.split("-"))): v for k, v in got_raw.items()}
        ref, dropped = ref_holidays_by_law(y)
        dropped_total += len(dropped)
        n += len(ref)
        for d in sorted(set(got) | set(ref)):
            if d not in ref:
                bad.append("%s 道具にだけある: %s" % (d, got[d]))
            elif d not in got:
                bad.append("%s 参照にだけある: %s" % (d, ref[d]))
            elif got[d] != L["hol_name"](ref[d]):
                bad.append("%s 名前が違う: 道具=%s 参照=%s"
                           % (d, got[d], L["hol_name"](ref[d])))
    rep.line("祝日 vs jpholiday(1949〜2099年)", n, bad)
    return dropped_total


async def check_law_gap(pg, rep):
    """★参照のほうが法律より広い、という差が「出ること自体」を確かめる。

    黙って合わせていないか、を見る番人。差が消えていたら、
    道具が参照に寄せられたか、参照が変わったかのどちらかなので気づきたい。
    """
    bad = []
    cases = [(D(1972, 5, 4), "国民の休日"), (D(1985, 5, 4), "国民の休日"),
             (D(1973, 2, 12), "振替休日")]
    for d, name in cases:
        got_raw = await pg.evaluate(READ_HOLIDAYS, d.year)
        in_tool = d.isoformat() in got_raw
        in_ref = d in ref_holidays(d.year)
        if in_tool:
            bad.append("%s を道具が %s にしている(法律の施行より前)" % (d, name))
        if not in_ref:
            bad.append("%s を参照が %s にしなくなった(jpholiday が変わった?)" % (d, name))
    # 施行のすぐ後は、両方が持っていること
    for d, name in [(D(1988, 5, 4), "国民の休日"), (D(1973, 4, 30), "振替休日")]:
        got_raw = await pg.evaluate(READ_HOLIDAYS, d.year)
        if d.isoformat() not in got_raw:
            bad.append("%s(%s の最初の適用)を道具が持っていない" % (d, name))
    rep.line("法律と参照の差が出ること自体", len(cases) + 2, bad)


async def check_diff(pg, rep, cases, L):
    """期間タブ。日数・年月日の内訳・週・営業日・土日・平日の祝日。"""
    bad = []
    await pg.click("#tab-diff")
    for a, b, incl in cases:
        await set_date(pg, "#d-from", a)
        await set_date(pg, "#d-to", b)
        if incl != await pg.is_checked("#d-incl"):
            await pg.click("#d-incl")
        await pg.wait_for_timeout(12)
        c = cards_to_map(await pg.evaluate(READ_CARDS, "#d-out"))
        s, e = (a, b) if a <= b else (b, a)
        lack = missing(c, ["days", "ymd", "weeks", "biz", "weekend", "holiday-weekday"])
        if lack:
            bad.append("%s〜%s カードが出ていない: %s" % (s, e, lack)); continue
        days = (e - s).days + (1 if incl else 0)
        if num_of(c["days"]["value"]) != days:
            bad.append("%s〜%s incl=%s 日数 道具=%s 参照=%d"
                       % (s, e, incl, c["days"]["value"], days))
        rd = relativedelta(e, s)
        want = L["ymd"](rd.years, rd.months, rd.days)
        if c["ymd"]["value"] != want:
            bad.append("%s〜%s 内訳 道具=%s 参照=%s" % (s, e, c["ymd"]["value"], want))
        if abs(num_of(c["weeks"]["value"]) - round(days / 7, 1)) > 1e-9:
            bad.append("%s〜%s 週数 道具=%s 参照=%.1f"
                       % (s, e, c["weeks"]["value"], days / 7))
        # 営業日・土日・平日の祝日 ─ numpy に数えさせる(休日一覧は jpholiday から)
        last = e if incl else e - dt.timedelta(days=1)
        if last >= s:
            hol = sorted(d for y in range(s.year, last.year + 1)
                         for d in ref_holidays_by_law(y)[0] if s <= d <= last)
            biz = int(np.busday_count(s, last + dt.timedelta(days=1),
                                      holidays=np.array(hol, dtype="datetime64[D]")))
            wknd = sum(1 for i in range((last - s).days + 1)
                       if (s + dt.timedelta(days=i)).weekday() >= 5)
            holw = sum(1 for d in hol if d.weekday() < 5)
        else:
            biz = wknd = holw = 0
        for k, want_n in [("biz", biz), ("weekend", wknd), ("holiday-weekday", holw)]:
            if num_of(c[k]["value"]) != want_n:
                bad.append("%s〜%s incl=%s %s 道具=%s 参照=%d"
                           % (s, e, incl, k, c[k]["value"], want_n))
    rep.line("期間(日数・内訳・週・営業日)", len(cases) * 6, bad)


async def check_add(pg, rep, cases, L):
    """加減算タブ。日・週・月・年・営業日。"""
    bad = []
    await pg.click("#tab-add")
    for base, n, unit in cases:
        await set_date(pg, "#a-base", base)
        await pg.fill("#a-n", str(n))
        await pg.select_option("#a-unit", unit)
        await pg.wait_for_timeout(12)
        c = cards_to_map(await pg.evaluate(READ_CARDS, "#a-out"))
        lack = missing(c, ["result", "iso", "wareki", "elapsed"])
        if lack:
            bad.append("%s %+d %s カードが出ていない: %s" % (base, n, unit, lack)); continue
        if unit == "day":
            want = base + dt.timedelta(days=n)
        elif unit == "week":
            want = base + dt.timedelta(weeks=n)
        elif unit == "month":
            want = base + relativedelta(months=n)
        elif unit == "year":
            want = base + relativedelta(years=n)
        else:
            hol = set()
            for y in range(base.year - 2, base.year + 3):
                hol |= set(ref_holidays_by_law(y)[0])
            want, left, step = base, abs(n), (1 if n >= 0 else -1)
            while left:
                want += dt.timedelta(days=step)
                if want.weekday() < 5 and want not in hol:
                    left -= 1
        if c["iso"]["value"] != want.isoformat():
            bad.append("%s %+d %s → 道具=%s 参照=%s"
                       % (base, n, unit, c["iso"]["value"], want))
            continue
        if c["result"]["value"] != L["fmt"](want, L):
            bad.append("%s %+d %s 表示 道具=%s 参照=%s"
                       % (base, n, unit, c["result"]["value"], L["fmt"](want, L)))
        if num_of(c["elapsed"]["value"]) != (want - base).days:
            bad.append("%s %+d %s 実日数 道具=%s 参照=%d"
                       % (base, n, unit, c["elapsed"]["value"], (want - base).days))
        w = to_wareki(want, L)
        if w and c["wareki"]["value"] != w:
            bad.append("%s %+d %s 和暦 道具=%s 参照=%s" % (base, n, unit, c["wareki"]["value"], w))
    rep.line("加減算(日・週・月・年・営業日)", len(cases) * 4, bad)


async def check_age(pg, rep, cases, L):
    """年齢・学年タブ。"""
    bad = []
    await pg.click("#tab-age")
    for birth, at in cases:
        await set_date(pg, "#g-birth", birth)
        await set_date(pg, "#g-at", at)
        await pg.wait_for_timeout(12)
        c = cards_to_map(await pg.evaluate(READ_CARDS, "#g-out"))
        lack = missing(c, ["age", "kazoe", "lived", "birth-dow", "grade"])
        if lack:
            bad.append("%s→%s カードが出ていない: %s" % (birth, at, lack)); continue
        age = relativedelta(at, birth).years                      # 第三者に数えさせる
        if num_of(c["age"]["value"]) != age:
            bad.append("%s→%s 満年齢 道具=%s 参照=%d" % (birth, at, c["age"]["value"], age))
        if num_of(c["kazoe"]["value"]) != at.year - birth.year + 1:
            bad.append("%s→%s 数え年 道具=%s" % (birth, at, c["kazoe"]["value"]))
        if num_of(c["lived"]["value"]) != (at - birth).days:
            bad.append("%s→%s 日数 道具=%s 参照=%d"
                       % (birth, at, c["lived"]["value"], (at - birth).days))
        if c["birth-dow"]["value"] != L["dow"](birth, L):
            bad.append("%s 曜日 道具=%s 参照=%s"
                       % (birth, c["birth-dow"]["value"], L["dow"](birth, L)))
        grade, fiscal = school_grade(birth, at)
        if c["grade"]["note"] != L["fiscal"](fiscal):
            bad.append("%s→%s 年度 道具=%s 参照=%s"
                       % (birth, at, c["grade"]["note"], L["fiscal"](fiscal)))
        want_label = L["grade"](grade)
        if c["grade"]["value"] != want_label:
            bad.append("%s→%s 学年 道具=%s 参照=%s"
                       % (birth, at, c["grade"]["value"], want_label))
    rep.line("年齢・学年", len(cases) * 6, bad)


async def check_wareki(pg, rep, cases, L):
    """和暦タブ。西暦→和暦と、和暦→西暦の往復。"""
    bad = []
    await pg.click("#tab-wareki")
    for d in cases:
        await set_date(pg, "#w-date", d)
        await pg.wait_for_timeout(12)
        c = cards_to_map(await pg.evaluate(READ_CARDS, "#w-out"))
        lack = missing(c, ["wareki", "fiscal", "dow", "yday"])
        if lack:
            bad.append("%s カードが出ていない: %s" % (d, lack)); continue
        want = to_wareki(d, L)
        if want and c["wareki"]["value"] != want:
            bad.append("%s 和暦 道具=%s 参照=%s" % (d, c["wareki"]["value"], want))
        fiscal = d.year - 1 if d.month < 4 else d.year
        if c["fiscal"]["value"] != L["fiscal"](fiscal):
            bad.append("%s 年度 道具=%s 参照=%s" % (d, c["fiscal"]["value"], L["fiscal"](fiscal)))
        if c["dow"]["value"] != L["dow"](d, L):
            bad.append("%s 曜日 道具=%s 参照=%s" % (d, c["dow"]["value"], L["dow"](d, L)))
        yday = d.timetuple().tm_yday
        if num_of(c["yday"]["value"]) != yday:
            bad.append("%s 通算日 道具=%s 参照=%d" % (d, c["yday"]["value"], yday))
        # 和暦 → 西暦(往復)。元号の名前は言語で違うので、部品から引き直す
        p = wareki_parts(d)
        if p:
            await pg.select_option("#w-era", L["era"](p[0]))
            await pg.fill("#w-y", str(p[1]))
            await pg.fill("#w-m", str(d.month))
            await pg.fill("#w-d", str(d.day))
            await pg.wait_for_timeout(12)
            c2 = cards_to_map(await pg.evaluate(READ_CARDS, "#w-out2"))
            if not c2 or c2["iso"]["value"] != d.isoformat():
                bad.append("%s 往復 道具=%s" % (d, c2.get("iso", {}).get("value")))
    rep.line("和暦・年度・通算日・往復", len(cases) * 5, bad)


async def check_wareki_errors(pg, rep, L):
    """和暦の入力が範囲外・存在しない日のとき、黙って通さないこと。"""
    bad = []
    await pg.click("#tab-wareki")
    cases = [("令和", 1, 4, 30, L["errs"][0]),    # 令和は5月1日から
             ("平成", 1, 1, 7, L["errs"][1]),     # 平成は1月8日から
             ("昭和", 64, 1, 8, L["errs"][2]),    # 1989-01-08 は平成
             ("令和", 2, 2, 30, L["errs"][3])]    # 2月30日
    for era_ja, wy, m, d, want in cases:
        era = L["era"](era_ja)
        await pg.select_option("#w-era", era)
        await pg.fill("#w-y", str(wy)); await pg.fill("#w-m", str(m)); await pg.fill("#w-d", str(d))
        await pg.wait_for_timeout(12)
        msg = await pg.eval_on_selector("#w-msg", "e => e.textContent")
        out = await pg.eval_on_selector("#w-out2", "e => e.innerHTML")
        if want not in msg or out.strip():
            bad.append("%s%d年%d月%d日 を拒まなかった(msg=%r)" % (era, wy, m, d, msg))
    rep.line("和暦の入力を拒むところ", len(cases), bad)


async def check_hol_table(pg, rep, years, L):
    """祝日一覧タブ。画面の表が holidays() と同じことと、土曜と重なる日数。"""
    bad = []
    await pg.click("#tab-hol")
    for y in years:
        await pg.fill("#h-year", str(y))
        await pg.wait_for_timeout(20)
        rows = await pg.evaluate(
            "() => Array.from(document.querySelectorAll('#h-out tr'))"
            ".map(r => Array.from(r.children).map(c => c.textContent.trim()))")
        # ★見出し行は「最初の3列の行」として落とす(言葉で判定しない。前は「日で終わり月を含む」
        #   で選んでいて、英語版では1行も残らなかった。日付が違う行を落とさないためにも
        #   ここは中身で選ばないほうがよい)
        ref, _ = ref_holidays_by_law(y)
        shown = [r for r in rows if len(r) == 3][1:]
        if len(shown) != len(ref):
            bad.append("%d年 表の行数 道具=%d 参照=%d" % (y, len(shown), len(ref)))
            continue
        for r, d in zip(shown, sorted(ref)):
            if r[0] != L["hol_date"](d):
                bad.append("%d年 日付 道具=%s 参照=%s" % (y, r[0], L["hol_date"](d)))
            if r[1] != L["wd"][(d.weekday() + 1) % 7]:
                bad.append("%d年 %s 曜日 道具=%s 参照=%s"
                           % (y, r[0], r[1], L["wd"][(d.weekday() + 1) % 7]))
            if r[2] != L["hol_name"](ref[d]):
                bad.append("%d年 %s 名称 道具=%s 参照=%s" % (y, r[0], r[2], L["hol_name"](ref[d])))
        tail = [r for r in rows if len(r) == 1][-1][0] if any(len(r) == 1 for r in rows) else ""
        want_sat = sum(1 for d in ref if d.weekday() == 5)
        m = re.search(L["summary"], tail)
        if not m or int(m.group(1)) != len(ref) or int(m.group(2)) != want_sat:
            bad.append("%d年 まとめ 道具=%r 参照=計%d日/土曜%d日" % (y, tail, len(ref), want_sat))
    rep.line("祝日一覧の表(画面の読み戻し)", len(years), bad)


# ============================ 見本を作る ============================

def make_cases(rng, n):
    def rnd(lo=1950, hi=2098):
        y = rng.randint(lo, hi)
        m = rng.randint(1, 12)
        return D(y, m, rng.randint(1, 28 if m == 2 else 30))

    diff = [(rnd(), rnd(), rng.random() < 0.5) for _ in range(n)]
    # 「薄い領域」対策に、手で置く形もまぜる(うるう年の2/29・年またぎ・同じ日・逆順・
    #  五輪で祝日が動いた年・法律の施行の前後)
    diff += [
        (D(2024, 2, 29), D(2025, 2, 28), True),
        (D(2024, 12, 31), D(2025, 1, 1), False),
        (D(2026, 5, 1), D(2026, 5, 1), True),
        (D(2026, 5, 6), D(2026, 4, 28), False),      # 逆順
        (D(2020, 7, 20), D(2020, 7, 27), True),      # 五輪で海の日が動いた週
        (D(2021, 8, 6), D(2021, 8, 10), True),       # 五輪で山の日が動いた週
        (D(1985, 5, 1), D(1986, 5, 7), True),        # 国民の休日の施行をまたぐ
        (D(1973, 4, 1), D(1973, 5, 7), True),        # 振替休日の施行をまたぐ
        (D(1999, 12, 25), D(2000, 1, 20), True),     # 成人の日の規則が変わる年
        (D(2019, 4, 25), D(2019, 5, 8), True),       # 即位の10連休
    ]
    units = ["day", "week", "month", "year", "biz"]
    add = [(rnd(), rng.randint(-400, 400), rng.choice(units)) for _ in range(n)]
    add += [
        (D(2026, 1, 31), 1, "month"),                # 存在しない日は末日に丸める
        (D(2024, 2, 29), 1, "year"),                 # うるう日の1年後
        (D(2026, 3, 31), -1, "month"),
        (D(2026, 5, 1), 0, "day"),
        (D(2019, 4, 26), 1, "biz"),                  # 10連休の直前
    ]
    age = []
    while len(age) < n:
        b = rnd(1930, 2020)
        a = rnd(max(b.year, 1950), 2098)
        if a >= b:                       # 生年月日が基準日より後は道具が拒む形(別の検査で見る)
            age.append((b, a))
    age += [
        (D(2019, 4, 1), D(2026, 5, 1)),              # 早生まれの境目(4月1日)
        (D(2019, 4, 2), D(2026, 5, 1)),              # その翌日
        (D(2024, 2, 29), D(2026, 2, 28)),            # うるう日生まれ
        (D(2000, 5, 6), D(2026, 5, 6)),              # 誕生日ちょうど
        (D(2000, 5, 6), D(2026, 5, 5)),              # 誕生日の前日
    ]
    wareki = [rnd(1873, 2098) for _ in range(n // 2)]
    wareki += [D(2019, 4, 30), D(2019, 5, 1), D(1989, 1, 7), D(1989, 1, 8),
               D(1926, 12, 25), D(1912, 7, 30)]      # 元号の切れ目ちょうど
    return diff, add, age, wareki


# ============================ わざと壊す ============================

SABOTAGE = [
    ("いまの規則を全部の年に当てる(9/1に直した傷そのもの)",
     ('push(y < 2000 ? mk(y,1,15) : nthMonday(y,1,2), "成人の日");',
      'push(nthMonday(y,1,2), "成人の日");')),
    ("春分の1980年より前の定数を落とす",
     ('const vernal  = y => y <= 1979\n'
      '  ? Math.floor(20.8357 + 0.242194*(y-1980) - Math.trunc((y-1983)/4))\n'
      '  : Math.floor(20.8431 + 0.242194*(y-1980) - Math.trunc((y-1980)/4));',
      'const vernal  = y => Math.floor(20.8431 + 0.242194*(y-1980) - Math.trunc((y-1980)/4));')),
    ("振替休日を施行の前にも当てる",
     ('      if (y === 1973 && dt < mk(1973,4,12)) return;', '')),
    ("国民の休日を施行の前にも当てる",
     ('  if (y >= 1986) {\n    const sorted', '  if (y >= 1949) {\n    const sorted')),
    ("2020年の五輪の移動をやめる",
     ('  if (y === 2020) push(mk(y,7,23), "海の日");', '  if (false) push(mk(y,7,23), "海の日");')),
    ("初日算入の +1 を落とす",
     ('  const days = rawDays + (incl ? 1 : 0);', '  const days = rawDays;')),
    ("月の加減算で末日に丸めるのをやめる",
     ('  return mk(ny, nm, Math.min(d, daysInMonth(ny, nm)));',
      '  return mk(ny, nm, d);')),
    ("満年齢を誕生日の当日に上げない",
     ('  const hadBirthday = at >= anniv;', '  const hadBirthday = at > anniv;')),
    ("満年齢の応当日を末日に丸めるのをやめる(9/1に直した傷そのもの)",
     ('                   Math.min(b.getDate(), daysInMonth(at.getFullYear(), b.getMonth()+1)));',
      '                   b.getDate());')),
    ("年月日の内訳を、足し戻らない形に戻す(9/1に直した傷そのもの)",
     ('  if (addMonths(s, total) > e) total--;', '  if (false) total--;')),
    ("早生まれの境目を4月1日でなく3月31日にする",
     ('  const schoolYearBase = (b.getMonth()+1 < 4 || (b.getMonth()+1 === 4 && b.getDate() === 1))',
      '  const schoolYearBase = (b.getMonth()+1 < 4)')),
    ("和暦の元年を1年と書く",
     ('label: `${e.name}${n === 1 ? "元" : n}年${MN[dt.getMonth()]}${dt.getDate()}日` };',
      'label: `${e.name}${n}年${MN[dt.getMonth()]}${dt.getDate()}日` };')),
    ("カードの名札(data-k)を落とす(検証がカードを引けなくなる)",
     ('<div class="card${hl ? " hl" : ""}${label === "" ? " wide" : ""}" data-k="${k}">',
      '<div class="card${hl ? " hl" : ""}${label === "" ? " wide" : ""}">')),
    ("月の名前の表を1つずらす(9/2に足した MN の取り違え)",
     ('const MN = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"];',
      'const MN = ["2月","1月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"];')),
    ("営業日の加減算で祝日を見ない",
     ('    while (left > 0) { r = addDays(r, step); if (isBusiness(r)) left--; }',
      '    while (left > 0) { r = addDays(r, step); if (!isWeekend(r)) left--; }')),
]


# ============================ 走らせる ============================

async def run(html_path, n, seed, quiet=False, lang="ja"):
    rng = random.Random(seed)
    diff, add, age, wareki = make_cases(rng, n)
    L = LANGS[lang]
    rep = Report()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(pathlib.Path(html_path).resolve().as_uri())
        dropped = await check_holidays(pg, rep, L)
        await check_law_gap(pg, rep)
        await check_diff(pg, rep, diff, L)
        await check_add(pg, rep, add, L)
        await check_age(pg, rep, age, L)
        await check_wareki(pg, rep, wareki, L)
        await check_wareki_errors(pg, rep, L)
        await check_hol_table(pg, rep,
                              [1949, 1973, 1986, 1999, 2000, 2019, 2020, 2021, 2026, 2099], L)
        if errs:
            rep.line("JSエラー", 0, errs)
        await b.close()
    if not quiet:
        rep.show()
        print("参照(jpholiday)が法律の施行より前に当てはめていた日: %d 件(道具は持たない側が正しい)"
              % dropped)
    return rep


async def sabotage(html_path, n, seed, lang="ja"):
    src = pathlib.Path(html_path).read_text(encoding="utf-8")
    tmp = pathlib.Path(html_path).with_name("_sabotage_date.html")
    print("わざと壊して、検査が捕まえるか見る(%d 種)\n" % len(SABOTAGE))
    missed = []
    try:
        for i, (name, (a, b)) in enumerate(SABOTAGE, 1):
            if a not in src:
                print("%2d. %-46s ★仕込めない(差し替え元が見つからない)" % (i, name))
                missed.append(name)
                continue
            tmp.write_text(src.replace(a, b, 1), encoding="utf-8", newline="\n")
            rep = await run(tmp, max(60, n // 4), seed + i, quiet=True, lang=lang)
            caught = [nm for nm, _ in rep.bad]
            if rep.ok():
                print("%2d. %-46s ★素通り" % (i, name))
                missed.append(name)
            else:
                print("%2d. %-46s 検出(%s)" % (i, name, sorted(set(caught))[0]))
    finally:
        if tmp.exists():
            tmp.unlink()
    print("\n素通り: %d / %d" % (len(missed), len(SABOTAGE)))
    for m in missed:
        print("  - " + m)
    return 1 if missed else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default=None)
    ap.add_argument("--lang", choices=sorted(LANGS), default="ja")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--sabotage", action="store_true")
    args = ap.parse_args()
    page = args.page or str(EN_PAGE if args.lang == "en" else DEFAULT_PAGE)
    print("当てるページ: %s (%s)" % (page, args.lang))
    if args.sabotage:
        return asyncio.run(sabotage(page, args.n, args.seed, args.lang))
    rep = asyncio.run(run(page, args.n, args.seed, lang=args.lang))
    return 0 if rep.ok() else 1


if __name__ == "__main__":
    sys.exit(main())
