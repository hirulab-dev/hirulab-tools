# 検証スクリプト

公開している道具のうち、「合っているか」を機械で確かめられるものはここにスクリプトを置いています。
どれも **ページの中の計算部分をそのまま取り出して**、別の実装・別のデータと突き合わせる形です。

| スクリプト | 何と突き合わせるか |
|---|---|
| `test_timezone.py` | [タイムゾーン変換](https://hirulab-dev.github.io/hirulab-tools/tz/) と Python の `zoneinfo`。72ゾーン × 2015〜2030年で 132,996 件 |

## 使い方

```
pip install playwright tzdata
python -m playwright install chromium
python tools/tests/test_timezone.py docs/tz/index.html --n 250
```

## 出力の読み方

**不一致** と **既知のデータ版差** を分けて数えます。後者は「ブラウザに入っている
タイムゾーンデータが Python 側より古い」ことによる差で、ツールの誤りではありません。
2026-08-22 時点では `America/Vancouver` と `Africa/Casablanca` の2件が該当します
(どちらも2026年秋以降の規則変更にブラウザのICUが追いついていない)。
ブラウザが追いつけば、この2件は自然に消えます。

スクリプト先頭の `KNOWN` に、その差をいつから既知とみなすかを日付つきで書いてあります。
**その日付より前で割れたら本物の不一致**として落ちます。
