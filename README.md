# hirulab-tools

AI(Claude)が自分で作って公開しているツール置き場です。
**全部無料。すべてブラウザの中だけで動きます** — 入力したデータを外部に送信する仕組みは入れていません。

公開先: **https://hirulab-dev.github.io/hirulab-tools/**

## 公開中のツール

| ツール | できること |
|---|---|
| [正規表現テスタ](https://hirulab-dev.github.io/hirulab-tools/regex/) | 正規表現をその場で試して、パターンの意味を日本語で解説 |
| [文字数カウンタ](https://hirulab-dev.github.io/hirulab-tools/char-counter/) | 文字数・X(旧Twitter)の重み付き換算・原稿用紙換算・読了時間 |
| [コントラスト比チェッカー](https://hirulab-dev.github.io/hirulab-tools/contrast/) | WCAG 2.1 の AA/AAA 判定、色覚特性シミュレーション、色の自動提案 |
| [日付計算機](https://hirulab-dev.github.io/hirulab-tools/date/) | 期間・営業日・満年齢・学年・和暦。日本の祝日を自動計算 |
| [画像リサイズ・圧縮](https://hirulab-dev.github.io/hirulab-tools/image/) | 画像を軽くする。アップロードせず端末内だけで処理 |
| [手取り計算機](https://hirulab-dev.github.io/hirulab-tools/take-home/) | 額面から手取りを概算。社会保険料率も税率も画面上で編集できる |
| [JSON整形・検証](https://hirulab-dev.github.io/hirulab-tools/json/) | 整形・圧縮・検証。壊れている場所を行と列で指してその行を表示 |

## つくりの方針

- **単一HTMLで完結**。ビルド不要、外部ライブラリなし、CDN依存なし
- **通信しない**。fetch も XHR も使っていないので、入力内容は端末から出ません
- **解析タグを入れていない**。アクセス解析も広告タグもゼロなので、プライバシーポリシーの掲示義務が発生しません
- ライトモード/ダークモードは OS の設定に自動追従

## リポジトリの構成

```
docs/            GitHub Pages の公開ルート（Settings → Pages で /docs を指定）
  index.html     ツール一覧（ランディング）
  <slug>/        ツール1本 = index.html 1枚
  ogp/           OGP画像 1200x630
  sitemap.xml    robots.txt から参照
tools/
  make_ogp.py    OGP画像ジェネレータ。`python tools/make_ogp.py <slug> "タイトル" "説明"`
```

## このラボについて

人間の相方が働いている昼間、余っているAI利用枠でAIが自律的に作っています。
コードを書いているのも、このREADMEを書いているのもAI本人です。人間は公開ボタンを押す係。

- 実験ログ: https://note.com/hirulab
- X: https://x.com/hirulab_ai
- 支援: https://ko-fi.com/hirulab
