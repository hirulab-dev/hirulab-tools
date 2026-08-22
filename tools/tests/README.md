# 検証スクリプト

公開している道具のうち、「合っているか」を機械で確かめられるものはここにスクリプトを置いています。
どれも **ページの中の計算部分をそのまま取り出して**、別の実装・別のデータと突き合わせる形です。

| スクリプト | 何と突き合わせるか |
|---|---|
| `test_timezone.py` | [タイムゾーン変換](https://hirulab-dev.github.io/hirulab-tools/tz/) と Python の `zoneinfo`。72ゾーン × 2015〜2030年で 132,996 件 |
| `test_csv.py` | [CSVプレビュー・診断](https://hirulab-dev.github.io/hirulab-tools/csv/) と Python の `csv`。ランダムに作った 2,300 ファイル・52,353 セル。文字コードと区切り文字の判定も同時に採点 |

## 使い方

```
pip install playwright tzdata
python -m playwright install chromium
python tools/tests/test_timezone.py docs/tz/index.html --n 250
python tools/tests/test_csv.py --page docs/csv/index.html --cases 800
```

## 出力の読み方

**不一致** と **既知のデータ版差** を分けて数えます。後者は「ブラウザに入っている
タイムゾーンデータが Python 側より古い」ことによる差で、ツールの誤りではありません。
2026-08-22 時点では `America/Vancouver` と `Africa/Casablanca` の2件が該当します
(どちらも2026年秋以降の規則変更にブラウザのICUが追いついていない)。
ブラウザが追いつけば、この2件は自然に消えます。

スクリプト先頭の `KNOWN` に、その差をいつから既知とみなすかを日付つきで書いてあります。
**その日付より前で割れたら本物の不一致**として落ちます。

## test_csv.py の考えかた

セルの正解は、**書き出す前に持っていた元の行そのもの**です。
ブラウザと同じ手順を Python で書き直しても、同じ勘違いをすれば同じ答えになって
気づけないので、参照側は「書き出す前の値」という別の出どころにしています
(`csv.writer` → `csv.reader` で往復できることは、そのつど別に確かめています)。

文字コードは UTF-8 / UTF-8 BOM / CP932 / EUC-JP / UTF-16 の5通りで書き出し、
判定器が当てられるかを数えます。**ASCIIだけになった回は「判定不要」として別に数えます**
(どの文字コードで読んでも同じ結果になるので、当たっても実力ではない)。
区切り文字も同様に、**どちらでも列数がそろってしまう形の回は除外**して数えます。
