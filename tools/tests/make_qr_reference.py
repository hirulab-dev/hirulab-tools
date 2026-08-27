#!/usr/bin/env python3
"""QRツール検証用の参照データを作る(segno = 独立実装)。

    python tools/tests/make_qr_reference.py            # tools/tests/qr-reference.json に書く
    python tools/tests/test_qr.py                      # それと突き合わせる

参照データ自体はサイズが大きいので git には入れない。必要なときにこれで作り直す。

★ segno の詰めビット処理を1か所だけ規格どおりに直してから使っている(2026-08-22 発見):
segno の write_padding_bits は `8 - (length % 8)` 個の 0 を足すため、
**すでに語の境界で終わっているときに 0 を8個(=語1つぶん)余計に足す**。
ISO/IEC 18004 7.4.10 は「境界で終わらない場合に」詰めビットを足すと書いているので、
正しくは `(8 - length % 8) % 8`。実害は「0x00 が1語余分に入る」だけで読み取りには影響しないが、
行列が1語ぶんずれるため、直さないと比較にならない。
"""
import json
import os
import random

import segno
from segno import consts, encoder


def _write_padding_bits(buff, version, length):
    if version not in (consts.VERSION_M1, consts.VERSION_M3):
        buff.extend([0] * ((8 - (length % 8)) % 8))


encoder.write_padding_bits = _write_padding_bits

ALNUM = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:")


def mode_of(t):
    if t.isdigit():
        return "numeric"
    if all(c in ALNUM for c in t):
        return "alphanumeric"
    return "byte"


def build_texts():
    random.seed(20260822)
    texts = [
        "HELLO WORLD", "https://hirulab-dev.github.io/hirulab-tools/",
        "1234567890", "8675309", "A", "0",
        "WIFI:T:WPA;S:hirulab-guest;P:p@ssw0rd!;;",
        "mailto:hi@example.com?subject=%E3%83%86%E3%82%B9%E3%83%88",
        "tel:0312345678", "geo:35.3392,139.4890",
        "日本語のテキストです。QRコードに入れます。", "SMSTO:09012345678:こんにちは",
    ]
    for n in [10, 40, 100, 300, 800, 1500, 2200]:
        texts.append("".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789 ") for _ in range(n)))
    for n in [20, 200, 1000, 4000, 7000]:
        texts.append("".join(random.choice("0123456789") for _ in range(n)))
    for n in [20, 200, 1000, 4000]:
        texts.append("".join(random.choice("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:") for _ in range(n)))
    for n in [30, 300, 700]:
        texts.append("".join(random.choice("あいうえお漢字テスト日本語") for _ in range(n)))
    return texts


def main():
    cases, skipped = [], 0
    for t in build_texts():
        mode = mode_of(t)
        for err in "lmqh":
            kw = dict(error=err, mode=mode, boost_error=False, micro=False, eci=False)
            if mode == "byte":
                kw["encoding"] = "utf-8"   # 漢字モードに逃げられると比較対象がずれる
            try:
                qr = segno.make(t, **kw)
            except Exception:
                skipped += 1                # その型番に入らない組み合わせは飛ばす
                continue
            cases.append({
                "text": t, "ecl": err.upper(), "version": qr.version, "mask": qr.mask,
                "size": len(qr.matrix),
                "matrix": ["".join(str(int(v)) for v in row) for row in qr.matrix],
            })
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qr-reference.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False)
    print("cases %d / skipped %d / versions %s"
          % (len(cases), skipped, sorted({c["version"] for c in cases})))


if __name__ == "__main__":
    main()
