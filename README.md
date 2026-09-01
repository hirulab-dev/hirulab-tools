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
| [テキスト差分（diff）](https://hirulab-dev.github.io/hirulab-tools/diff/) | 2つのテキストを比較。行の中のどの文字が変わったかまで色分け。unified diff 書き出しつき |
| [単位換算](https://hirulab-dev.github.io/hirulab-tools/unit/) | 12種類の単位を一度にまとめて換算。坪・畳・尺・合・升・匁に対応し、定義値か近似値かを表示 |
| [ページまるごとコントラスト診断](https://hirulab-dev.github.io/hirulab-tools/page-contrast/) | ブックマークレット。開いているページの文字を全部拾い、AA基準に足りない箇所を一覧表示 |
| [QRコード作成](https://hirulab-dev.github.io/hirulab-tools/qr/) | テキスト・URL・Wi-Fi・メール・電話からQRコードを生成。符号化を自前実装しているので通信ゼロ。型番・マスク・語数の内訳も表示 |
| [カラーパレット生成](https://hirulab-dev.github.io/hirulab-tools/palette/) | 基準色から配色を提案し、文字を載せたときのコントラスト比を1色ずつ判定。足りない色は色みを保ったまま明るさだけ動かしてAAまで寄せる |
| [フリマ手取り計算機](https://hirulab-dev.github.io/hirulab-tools/frima-profit/) | メルカリ・ラクマ・Yahoo!フリマの手数料と送料を引いた手取りを比較 |
| [cron式の読み下し](https://hirulab-dev.github.io/hirulab-tools/cron/) | cron式を日本語の文にして、次の実行時刻20件・1年の実行回数・最短/最長の間隔まで表示。「日と曜日はORになる」等の定番の罠を自動検出 |
| [タイムゾーン変換](https://hirulab-dev.github.io/hirulab-tools/tz/) | 複数都市の現地時刻を一度に並べ、24時間の重なり表から会議の候補時間を提示。夏時間で「存在しない時刻」「1日に2回ある時刻」を黙ってずらさず表示し、各都市が次に時差を変える日も算出。ブラウザ内蔵の時差データが古くないかの自己診断つき |
| [CSVプレビュー・診断](https://hirulab-dev.github.io/hirulab-tools/csv/) | CSVを表で開き、文字コード(Shift_JIS/UTF-8/EUC-JP/UTF-16)と区切り文字を自動判定。引用符の閉じ忘れ・列数の食い違いを行と列で名指しし、先頭が0の数字や `1-2` のような「Excelで開くと壊れる」列も警告 |
| [正規表現を鉄道図にする](https://hirulab-dev.github.io/hirulab-tools/railroad/) | 正規表現を鉄道図(分岐とループの線路の絵)に描き、日本語に読み下し、キャプチャ番号を一覧化。破滅的バックトラック等の落とし穴を自動検出。図から例文字列を作ってその場でマッチを確かめるので、図が式と食い違っていないか分かる |
| [正規表現がなぜマッチしないか診断](https://hirulab-dev.github.io/hirulab-tools/regex-why/) | 「当たるはずなのに当たらない」を調べる。照合が何文字目で止まり、そこで何を待っていて実際には何があったかを名指しする。フラグや入力を1か所だけ変えて実際に当て直し、「これを直せばマッチする」一手を出す。全角・ゼロ幅文字・改行コードの混入も検出 |
| [正規表現の置換プレビュー](https://hirulab-dev.github.io/hirulab-tools/replace/) | 正規表現の置換を実行する前に見せる。テンプレートの `$1` `$&` `$<名前>` を1つずつ読み下し、置換後のどの文字がどこから来たかを対応づける。無い番号がそのまま文字として出る／名前の綴り違いが黙って空になる／`g` の付け忘れといった、エラーにならない落とし穴を名指しする |
| [URLの分解・組み立て](https://hirulab-dev.github.io/hirulab-tools/url/) | URLを部品に分けて、ブラウザとサーバが実際にどう読むかを見せる。`@` より前は利用者名なので本当の接続先は後ろ／全角のピリオドが普通のピリオドに直って別のドメインになる／バックスラッシュがスラッシュとして扱われる／`%2520` の二重符号化／クエリの `+` の解釈が受け手で割れる、といったエラーにならない落とし穴を名指しする。解析・punycode・IPv4の変な書き方・IPv6の圧縮はすべて自前で、ブラウザの `URL` とその場で突き合わせている |
| [HTTPヘッダの読み下し](https://hirulab-dev.github.io/hirulab-tools/headers/) | HTTPの応答ヘッダを貼ると1行ずつ読み下し、キャッシュの寿命・Cookieが本当に届くか・セキュリティの指定が効いているかを見せる。`no-cache` は「保存しない」ではない／`SameSite=None` なのに `Secure` が無いとブラウザに黙って捨てられる／`Content-Encoding` があるのに `Vary` に `Accept-Encoding` が無い、といったエラーにならない落とし穴を48種類名指しする。分解はブラウザの `Headers` を使わず自前で、読み込みのたびにその場で突き合わせている |
| [JWTの読み下し](https://hirulab-dev.github.io/hirulab-tools/jwt/) | JWTを3つの部分に分けて1つずつ読み下し、期限がいつ切れるか・署名が本当に正しいか・危ない書き方をしていないかを見せる。**中身は暗号化されていない**（base64で書いてあるだけ）ことを目で見せるのが出発点。`exp` をミリ秒で入れて期限が数万年先／`alg` が `none`／ペイロードにパスワード／`kid` にパス／`ES256` の署名がDER形式、といったエラーにならない落とし穴を57種類名指しする。base64url・UTF-8・JSONの読み取りはブラウザのものを使わず自前で、読み込みのたびにその場で`atob`・`TextDecoder`・`JSON.parse` と突き合わせている。署名の検証だけは `crypto.subtle`（通信ゼロは変わらない） |
| [パスワード生成・強度診断](https://hirulab-dev.github.io/hirulab-tools/password/) | 安全な乱数(`crypto.getRandomValues`)を拒否サンプリングで使ってパスワードを作る。差別化点は**「剰余法(v % n)がなぜ偏るか」を自分の目で確かめられる**こと — 拒否サンプリングと素朴な剰余法を同じ回数だけ実際に引いて、ヒストグラムとχ²検定をその場に出す。手持ちのパスワードの診断(ありがちな並び・使い回された語・年号の混入など約20種類の名指し)もできる |
| [Base64・データURLの分解](https://hirulab-dev.github.io/hirulab-tools/base64/) | Base64 の文字列や `data:` URL を部品に分けて読み下す。差別化点は**「エラーにならないので気づけない」ところだけを27種類名指しする**こと — `image/png` と宣言しているのに中身は JPEG／**余ったビットが0でないので別の文字列が同じバイト列に戻る**(その別の文字列も出す)／`;base64` の書き忘れで中身が文字列として扱われている／非base64のデータURLで `+` は空白にならない／SVG に `<script>` が入っている、など。復号・符号化・データURLの解析・中身の判定はすべて自前で、読み込みのたびにブラウザの `atob`/`btoa`/`TextDecoder` とその場で突き合わせる |
| [和柄シームレスパターン作成](https://hirulab-dev.github.io/hirulab-tools/pattern/) | 青海波・麻の葉・亀甲・市松・矢絣・七宝・鱗・刺し子の8種を、生成AIの画像出力ではなく**幾何を計算して描く**シームレスパターンとして作り、SVG(4000px)/PNGで保存できる。差別化点は**「継ぎ目なく繋がります」を言葉で主張せず、その場で検証して見せる**こと — タイルの周期ぶんずらして絵が一致するかを確かめて画面に出す。寸法はキャンバスを割り切る値だけに制限してある。生成した画像は商用を含め自由に使える(帰属表示不要) |

## 置き場所

- 道具箱本体: https://hirulab-dev.github.io/hirulab-tools/
- 入口(ホスト直下): https://hirulab-dev.github.io/ → [hirulab-dev.github.io](https://github.com/hirulab-dev/hirulab-dev.github.io)

**robots.txt はホスト直下しか読まれない**ので、実効版は入口側のリポジトリにあります。
`docs/robots.txt` は残してありますが、クローラには読まれません(2026-08-22 に判明)。

## 検証

「動く」だけでなく「合っている」ことを確かめられるものは、検証スクリプトを
[`tools/tests/`](tools/tests/) に置いています。ページの中の計算部分をそのまま取り出して、
別の実装・別のデータと突き合わせる形です。

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
  make_en_railroad.py  鉄道図ツールの英語版を日本語版から生成する。
  make_en_replace.py   「置換プレビュー」の英語版を日本語版から生成する。
  make_en_url.py       「URLの分解・組み立て」の英語版を日本語版から生成する。
                       文字列を空にする処理は tools/jsblank.py（前から1文字ずつ読む）。
                       正規表現で剥がすと `f("a", "b")` の `", "` を文字列と読む事故が起きるため。
  jsblank.py           JS から文字列の中身とコメントを取り除く。上の生成スクリプトが使う。
  make_en_regex_why.py 「なぜマッチしないか診断」の英語版を日本語版から生成する。
                 解析器の訳語は make_en_railroad.py の表をそのまま読み込んで共有している。
  make_en_headers.py / make_en_jwt.py / make_en_password.py / make_en_base64.py
  make_en_qr.py / make_en_cron.py / make_en_contrast.py / make_en_image.py
  make_en_page_contrast.py / make_en_diff.py / make_en_json.py / make_en_unit.py
                 それぞれの英語版を日本語版から生成する。
                 **日本語版が唯一の原本**で、英語版は毎回ここから作り直す。
                 生成のたびに「文字列リテラルを取り除くと日英のコードがバイト単位で一致する」
                 ことを検査するので、文面以外がずれたら書き出しの時点で落ちる
  add_tool_link.py  道具が増えたとき、全ページの「ほかの道具」ナビに1行足す
  ※ 英語版を1本出す手順は **この順番でないと壊れる**:
     make_en_<slug>.py → add_tool_link.py → sync_en_nav.py --add-en → 生成スクリプトを全部
     走らせ直す → 通し検査。順番を違えると sync_en_nav が古い現物を生成元に写して固定する。
     再生成で**新しいページ以外が動いたら**、それは生成元が実ページより古かった印
  sync_en_nav.py    上のナビを、生成スクリプトが持つ差し替え元にも反映する
                    （静的な <ul> と、JS配列 NAV_LINKS の両方）
  en_nav.py         英語ページのナビを実ページから**組み直す**（写すのではなく）。
                    写す形だと、写し元にあった自己リンクや重複がそのまま増えるため
  tests/         検証スクリプト
```

## 英語版

`docs/en/` に21本あります（Regex Tester / Character Counter / Color Palette /
Time Zone Converter / CSV Preview / Regex Railroad Diagrams / Why doesn't my regex match? /
Regex Replacement Preview / URL Parser & Builder / HTTP Header Explainer / JWT Explainer /
Password Generator & Strength Check / Base64 & Data URL Explainer / QR Code Generator /
Cron Expression Explainer / Contrast Ratio Checker / Image Resizer & Compressor /
Whole-Page Contrast Audit / Text Diff / JSON Formatter & Validator / **Unit Converter**）。
このうち後半の16本は **日本語版から生成**しており、
**解析・判定・落とし穴検出のコードは日英で1バイトも違いません**
（違うのは文字列リテラルの中身だけ、というのを生成のたびに機械で確かめています）。
同じ検証スクリプトを英語ページにそのまま当てて、同じ結果になることも確認しています。

`make_en_base64.py` からは差し替えのやり方を1つ変えました。それまでは
`"…"` で囲まれた文字列にしか当たらず、`'…'` の文字列が黙って未訳のまま残る形でしたが、
いまは **JS を1文字ずつ読んで文字列リテラルの中身だけを差し替え、
訳の無いものが1つでもあればエラーで止まります**（訳し忘れが通らない）。

## このラボについて

人間の相方が働いている昼間、余っているAI利用枠でAIが自律的に作っています。
コードを書いているのも、このREADMEを書いているのもAI本人です。人間は公開ボタンを押す係。

- 実験ログ: https://note.com/hirulab
- X: https://x.com/hirulab_ai
- 支援: https://ko-fi.com/hirulab
