#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""対象外(skip)の件数を見張る。

2026-08-23 に踏んだ穴の再発防止。
test_replace.py の --sabotage で仕込んだバグの1つが、どの検査にも捕まらなかった。
原因は「打ち切りに掛かった件を対象外に落としていた」こと。
壊れると打ち切りに掛かるので、**壊れた分だけまるごと検査の外に出ていた**。

除外は「見なくていい」と宣言することなので、
**除外の理由がバグと相関していたら、その検査は成立しない**。
だから対象外の数そのものを、毎回目に見えるところに出して、前回と比べる。

使い方（検査スクリプト側）:

    from skipwatch import SkipWatch
    sw = SkipWatch("test_replace")           # スクリプト名
    ...
    sw.check("[1] 置換結果の照合", skipped=r1["skip"], total=len(cases))
    ...
    sys.exit(sw.report())                    # 0=OK / 1=要確認

基準値は `skip-baseline.json` に貯める。初回はその場で記録するだけなので、
既存の検査に足しても余計な実行は要らない。
更新は `--update-skip-baseline`（各スクリプトが素通しする）。
"""

import json
import os
import sys

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skip-baseline.json")

# 基準からこの割合ぶん増えたら知らせる（0.05 = 5ポイント）
TOLERANCE = 0.05
# 基準が無くても、これを超える対象外は無条件で知らせる
ABSOLUTE_FLOOR = 0.30


def _load():
    try:
        with open(BASELINE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(data):
    with open(BASELINE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


class SkipWatch:
    def __init__(self, script, update=None):
        self.script = script
        # 呼び出し側が渡さなければ argv を見る（各スクリプトに引数追加を強いない）
        self.update = ("--update-skip-baseline" in sys.argv) if update is None else update
        self.data = _load()
        self.rows = []      # (ラベル, 対象外, 母数, 状態)
        self.dirty = False

    def check(self, label, skipped, total):
        """対象外の件数を1つ記録して、基準と比べる。

        total は「対象外も含めた母数」。skipped/total が対象外の割合。
        """
        skipped, total = int(skipped), int(total)
        ratio = (skipped / total) if total else 0.0
        key = "%s / %s" % (self.script, label)
        base = self.data.get(key)

        if self.update or base is None:
            self.data[key] = {"skipped": skipped, "total": total, "ratio": round(ratio, 6)}
            self.dirty = True
            state = "基準を更新" if base is not None else "基準を記録"
        elif ratio > base["ratio"] + TOLERANCE:
            state = "★増えた（基準 %.1f%%）" % (base["ratio"] * 100)
        elif ratio > ABSOLUTE_FLOOR:
            state = "★多い"
        elif ratio + TOLERANCE < base["ratio"]:
            # 減るのは悪いことではないが、母数の作り方が変わった合図なので出す
            state = "減った（基準 %.1f%%）" % (base["ratio"] * 100)
        else:
            state = "前回どおり"

        self.rows.append((label, skipped, total, ratio, state))
        return ratio

    def report(self):
        """まとめて出す。戻り値は終了コード（0=OK / 1=要確認）。"""
        if not self.rows:
            return 0
        if self.dirty:
            _save(self.data)

        width = max(len(r[0]) for r in self.rows)
        print("\n--- 対象外にした件数（除外がバグを隠していないか） ---")
        bad = 0
        for label, skipped, total, ratio, state in self.rows:
            mark = "★" if state.startswith("★") else " "
            print("%s %-*s  %6d / %6d  = %5.1f%%   %s"
                  % (mark, width, label, skipped, total, ratio * 100, state))
            if state.startswith("★"):
                bad += 1
        if bad:
            print("\n★ が付いた行は、検査が静かに縮んでいる可能性がある。")
            print("  ・壊したつもりが「対象外」に流れていないか")
            print("  ・母数の作り方を変えたのなら --update-skip-baseline で基準を更新する")
        return 1 if bad else 0


if __name__ == "__main__":
    data = _load()
    if not data:
        print("基準はまだ記録されていない（各検査スクリプトを1回ずつ回すと貯まる）")
        sys.exit(0)
    print("記録されている基準: %d 件\n" % len(data))
    width = max(len(k) for k in data)
    for key in sorted(data):
        v = data[key]
        print("%-*s  %6d / %6d = %5.1f%%" % (width, key, v["skipped"], v["total"], v["ratio"] * 100))
