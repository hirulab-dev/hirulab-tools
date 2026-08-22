#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""タイムゾーン変換ツールの検証。

ページ内の JS コア（/*==CORE-START==*/ 〜 /*==CORE-END==*/）を Chromium に読ませ、
Python の zoneinfo（別のタイムゾーンデータ）と突き合わせる。

    python lab/scripts/test_timezone.py <index.htmlのパス> [--n 400] [--seed 42]

見るもの:
  A. ある瞬間の時差と現地の壁時計（tzOffsetSec / tzParts）
  B. 壁時計 → 瞬間（wallToInstants）。0個=存在しない / 1個 / 2個=2回ある
  C. 時差が変わる瞬間（transitionsBetween）。Python 側は15分刻みの総当たりで見つける
     ＝ブラウザ側の「1時間刻み＋二分探索」とは別のやり方で照合する

注意: ブラウザ（ICU）と Python（tzdata パッケージ）はタイムゾーンデータの版が違うことがある。
食い違いが出たら、まずどちらの版が新しいかを疑う。実際 2026-08-22 の初回実行で
America/Vancouver と Africa/Casablanca が割れ、どちらも「ブラウザ側が古い」だった（下の KNOWN）。
"""
import argparse
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

CORE_RE = re.compile(r"/\*==CORE-START==\*/(.*?)/\*==CORE-END==\*/", re.S)

UTC = timezone.utc

# 素直なもの・半端なオフセット・南半球・30分だけ動くもの・年4回動くもの・
# 最近まで夏時間をやっていたもの・やめたもの、をひととおり混ぜる。
ZONES = [
    "UTC", "Asia/Tokyo", "Asia/Seoul", "Asia/Shanghai", "Asia/Taipei", "Asia/Hong_Kong",
    "Asia/Singapore", "Asia/Bangkok", "Asia/Jakarta", "Asia/Manila", "Asia/Ho_Chi_Minh",
    "Asia/Kolkata", "Asia/Kathmandu", "Asia/Karachi", "Asia/Dubai", "Asia/Tehran",
    "Asia/Jerusalem", "Asia/Gaza", "Asia/Beirut", "Asia/Amman", "Asia/Damascus",
    "Europe/Istanbul", "Europe/Moscow", "Europe/Kyiv", "Europe/Warsaw", "Europe/Berlin",
    "Europe/Paris", "Europe/Zurich", "Europe/Rome", "Europe/Madrid", "Europe/Lisbon",
    "Europe/Dublin", "Europe/London", "Atlantic/Azores", "Atlantic/Reykjavik",
    "Africa/Casablanca", "Africa/Lagos", "Africa/Cairo", "Africa/Nairobi",
    "Africa/Johannesburg", "Africa/Windhoek",
    "America/St_Johns", "America/New_York", "America/Toronto", "America/Chicago",
    "America/Mexico_City", "America/Denver", "America/Phoenix", "America/Los_Angeles",
    "America/Vancouver", "America/Anchorage", "America/Adak", "Pacific/Honolulu",
    "America/Sao_Paulo", "America/Argentina/Buenos_Aires", "America/Santiago",
    "America/Lima", "America/Bogota", "America/Havana", "America/Asuncion",
    "Australia/Perth", "Australia/Brisbane", "Australia/Adelaide", "Australia/Sydney",
    "Australia/Lord_Howe", "Pacific/Auckland", "Pacific/Chatham", "Pacific/Fiji",
    "Pacific/Apia", "Pacific/Kiritimati", "Pacific/Guam", "Antarctica/Troll",
]

YEAR_FROM, YEAR_TO = 2015, 2030

# ---------------------------------------------------------------------------
# 既知のデータ版の差（ツールの誤りではない）
#
# Playwright が持ってくる Chromium の ICU は、Python 側の tzdata パッケージより
# 版が古いことがある。2026-08-22 時点で実際に割れたのは次の2件で、どちらも
# 「新しい規則をブラウザがまだ知らない」側の差だった。
#   ・America/Vancouver … 2026-11 の秋の戻しが消える（恒久サマータイム化とみられる）。
#     Python は -07:00 のまま／ブラウザは -08:00 に戻す
#   ・Africa/Casablanca … 2026 年秋以降の切替が消え、UTC+00 のままになる。
#     Python は +00:00／ブラウザは +01:00 のまま
# ※「なぜ変わったか」はデータからは分からない。ここに書けるのは「切替が消えた」まで。
# この日付以降の食い違いだけを「既知の差」として仕分ける。日付より前で割れたら
# それは本物の不一致なので落とす。
# ---------------------------------------------------------------------------
KNOWN = {
    "America/Vancouver": (
        int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp() * 1000),
        "2026年秋以降 時計を戻さなくなる（IANA 2026c）。ブラウザのICUが未対応"),
    "Africa/Casablanca": (
        int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp() * 1000),
        "2026年秋以降 UTC+00 のまま（IANA 2026c）。ブラウザのICUが未対応"),
}


def is_known(kind, zone, key):
    """食い違いが「既知のデータ版差」の範囲に入っているか。"""
    if zone not in KNOWN:
        return False
    since, _why = KNOWN[zone]
    if kind == "C":                      # key は年
        return datetime(key + 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1000 > since
    if kind == "A":                      # key はミリ秒
        return key >= since
    if kind == "B":                      # key は壁時計
        return datetime(key["y"], key["mo"], key["d"],
                        tzinfo=timezone.utc).timestamp() * 1000 >= since
    return False


# ---------------------------------------------------------------------------
# Python 側の答え
# ---------------------------------------------------------------------------
def py_offset_and_wall(zone, ms):
    dt = datetime.fromtimestamp(ms / 1000, tz=UTC).astimezone(ZoneInfo(zone))
    return (int(dt.utcoffset().total_seconds()),
            dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)


def py_wall_to_instants(zone, w):
    """壁時計に対応する瞬間の一覧。fold=0/1 の両方を試し、
    「戻したら同じ壁時計になるか」で存在するものだけ残す。"""
    zi = ZoneInfo(zone)
    naive = datetime(w["y"], w["mo"], w["d"], w["h"], w["mi"], w["s"])
    out = []
    for fold in (0, 1):
        u = naive.replace(tzinfo=zi, fold=fold).astimezone(UTC)
        if u.astimezone(zi).replace(tzinfo=None, fold=0) == naive:
            ms = int(u.timestamp() * 1000)
            if ms not in out:
                out.append(ms)
    return sorted(out)


def py_transitions(zone, start_ms, end_ms, step_sec=900):
    """15分刻みの総当たりで変わり目を挟み、そこから1秒まで二分探索で詰める。
    ブラウザ側（1時間刻み）とは刻みも探し方も別にしてある。"""
    zi = ZoneInfo(zone)

    def off(ms):
        return int(datetime.fromtimestamp(ms // 1000, tz=UTC)
                   .astimezone(zi).utcoffset().total_seconds())

    out = []
    prev = off(start_ms)
    t = start_ms
    step = step_sec * 1000
    while t < end_ms:
        nxt = min(t + step, end_ms)
        cur = off(nxt)
        if cur != prev:
            lo, hi = t, nxt
            while hi - lo > 1000:
                mid = lo + ((hi - lo) // 2000) * 1000
                if mid <= lo:
                    break
                if off(mid) == prev:
                    lo = mid
                else:
                    hi = mid
            out.append((hi, prev, off(hi)))
            prev = cur
        t = nxt
    return out


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--n", type=int, default=400, help="1ゾーンあたりのランダム瞬間の数")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    src = open(args.html, encoding="utf-8").read()
    m = CORE_RE.search(src)
    if not m:
        print("CORE ブロックが見つからない", file=sys.stderr)
        return 2
    core = m.group(1)

    rng = random.Random(args.seed)
    lo_ms = int(datetime(YEAR_FROM, 1, 1, tzinfo=UTC).timestamp() * 1000)
    hi_ms = int(datetime(YEAR_TO + 1, 1, 1, tzinfo=UTC).timestamp() * 1000)

    fails = []
    known_diffs = []
    counts = {"A": 0, "B": 0, "C": 0}

    def record(kind, zone, key, got, want):
        (known_diffs if is_known(kind, zone, key) else fails).append(
            (kind, zone, key, got, want))

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto("about:blank")
        page.add_script_tag(content=core)
        icu = page.evaluate("() => { try { return Intl.DateTimeFormat()"
                            ".resolvedOptions().timeZone + ' / zones:' + "
                            "(Intl.supportedValuesOf ? Intl.supportedValuesOf('timeZone').length : '?') }"
                            " catch(e) { return 'n/a' } }")
        print(f"ブラウザ側: {icu}")

        # ---- A: 時差と壁時計 --------------------------------------------
        print("A. 時差と現地の壁時計 ...", end="", flush=True)
        for zone in ZONES:
            stamps = [rng.randrange(lo_ms, hi_ms) // 1000 * 1000 for _ in range(args.n)]
            got = page.evaluate(
                """([zone, list]) => list.map(ms => {
                     const p = tzParts(zone, ms);
                     return [tzOffsetSec(zone, ms), p.y, p.mo, p.d, p.h, p.mi, p.s];
                   })""", [zone, stamps])
            for ms, g in zip(stamps, got):
                counts["A"] += 1
                want = py_offset_and_wall(zone, ms)
                if tuple(g) != want:
                    record("A", zone, ms, tuple(g), want)
        print(f" {counts['A']:,}件")

        # ---- B: 壁時計 → 瞬間 -------------------------------------------
        # ランダムな壁時計に加えて、切替の前後30時間を1分刻みで舐める
        print("B. 壁時計から瞬間を求める ...", end="", flush=True)
        for zone in ZONES:
            walls = []
            for _ in range(args.n // 2):
                d = datetime.fromtimestamp(rng.randrange(lo_ms, hi_ms) / 1000, tz=UTC)
                walls.append({"y": d.year, "mo": d.month, "d": d.day,
                              "h": d.hour, "mi": d.minute, "s": 0})
            # 切替の周り（ここに存在しない時刻と2回ある時刻が集まる）
            for (at, _b, _a) in py_transitions(zone, lo_ms, hi_ms, step_sec=3600)[:14]:
                base = datetime.fromtimestamp(at / 1000, tz=UTC)
                for k in range(-90, 91):
                    d = (base + timedelta(minutes=k)).astimezone(ZoneInfo(zone))
                    walls.append({"y": d.year, "mo": d.month, "d": d.day,
                                  "h": d.hour, "mi": d.minute, "s": 0})
            got = page.evaluate(
                "([zone, list]) => list.map(w => wallToInstants(zone, w))", [zone, walls])
            for w, g in zip(walls, got):
                counts["B"] += 1
                want = py_wall_to_instants(zone, w)
                if [int(x) for x in g] != want:
                    record("B", zone, w, [int(x) for x in g], want)
        print(f" {counts['B']:,}件")

        # ---- C: 切替の瞬間 -----------------------------------------------
        print("C. 時差が変わる瞬間 ...", end="", flush=True)
        for zone in ZONES:
            for year in range(YEAR_FROM, YEAR_TO + 1):
                s = int(datetime(year, 1, 1, tzinfo=UTC).timestamp() * 1000)
                e = int(datetime(year + 1, 1, 1, tzinfo=UTC).timestamp() * 1000)
                got = page.evaluate(
                    "([zone, s, e]) => transitionsBetween(zone, s, e)"
                    ".map(t => [t.at, t.before, t.after])", [zone, s, e])
                got = [tuple(int(v) for v in t) for t in got]
                want = py_transitions(zone, s, e)
                counts["C"] += max(len(got), len(want), 1)
                if got != want:
                    record("C", zone, year, got, want)
        print(f" {counts['C']:,}件")

        browser.close()

    total = sum(counts.values())
    print(f"\n合計 {total:,} 件の照合")
    print(f"  不一致            {len(fails)} 件")
    print(f"  既知のデータ版差  {len(known_diffs)} 件")

    if known_diffs:
        by_zone = {}
        for f in known_diffs:
            by_zone.setdefault(f[1], []).append(f)
        print("\n［既知のデータ版差］ブラウザのタイムゾーンデータが Python より古い箇所")
        for zone in sorted(by_zone):
            print(f"  {zone}: {len(by_zone[zone])}件 — {KNOWN[zone][1]}")
            f = by_zone[zone][0]
            print(f"    例）{f[0]} 入力 {f[2]} / ブラウザ {f[3]} / Python {f[4]}")

    if fails:
        shown = {}
        for f in fails:
            shown.setdefault(f[0] + " " + f[1], []).append(f)
        for key in sorted(shown):
            group = shown[key]
            print(f"\n■ 不一致 {key}（{len(group)}件）")
            for f in group[:3]:
                print(f"   入力 {f[2]}")
                print(f"   ブラウザ {f[3]}")
                print(f"   Python   {f[4]}")
        return 1
    print("\n既知のデータ版差を除いて全一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
