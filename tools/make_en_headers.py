#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「HTTPヘッダの読み下し」の英語版を、日本語版から作る（2026-08-24）。

`make_en_railroad.py` / `make_en_regex_why.py` / `make_en_replace.py` /
`make_en_url.py` と同じ方式。**日本語版が唯一の原本**で、英語版は毎回ここから作り直す。

やっていること
1. HTML（head・本文・解説・ナビ・脚注）を英語の版に差し替える
2. スクリプトの中の**引用符で囲まれた文字列だけ**を英語に差し替える
3. できた英語版について、**「文字列リテラルの中身を全部空にすると、
   日本語版とバイト単位で一致する」**ことを確かめる。通れば、ヘッダの分解・
   キャッシュの寿命の計算・落とし穴の検出は1バイトも違わない
4. 画面に出るところに日本語が1文字も残っていないことを確かめる（コードのコメントは対象外）

使い方: python lab/scripts/make_en_headers.py <リポジトリの docs>
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank
from en_common import comments, translate_comments, translate_css_comments

# ★2026-09-03 夜 追加(コメントも訳す)。⚠ 訳は行数を変えない・訳の中に日本語を書かない。
COMMENTS = {
    '/* ------------------------------------------------------------------\n'
    '   RFC 9110 / 9112 をなぞったヘッダの分解。ブラウザの Headers は使わない\n'
    '   （使ったら「ブラウザと一致するか」を確かめる意味が無くなる）。\n'
    '   ------------------------------------------------------------------ */':
    '/* ------------------------------------------------------------------\n'
    '   Header parsing that follows RFC 9110 / 9112. The browser Headers class is\n'
    '   not used (using it would defeat the point of comparing against a browser).\n'
    '   ------------------------------------------------------------------ */',

    '/* 引用符は文字コードで書く（英語版の照合のため） */':
    '/* The quote is written as a character code, for the cross-language comparison */',
    '/* 値に置けるのは VCHAR / SP / HTAB / obs-text(0x80-0xFF)。制御文字は置けない。 */':
    '/* A value may hold VCHAR / SP / HTAB / obs-text (0x80-0xFF). Control characters may not. */',
    '/* 一度しか置けないヘッダ（複数来たら受け手によって扱いが割れる） */':
    '/* Headers that may appear only once (recipients disagree when they repeat) */',

    '/* 空白は「名前に置けない文字」より先に見る。トリムしてから token かどうかを見ると、\n'
    '       Content-Type : のような形を黙って通してしまう（実際そう書いていて、プリセットで見つけた）。 */':
    '/* Whitespace is checked before the invalid-name characters: trimming first and then\n'
    '       testing for a token silently accepts forms like Content-Type : (a preset found it). */',

    '/* 同じ名前が複数来たときの結合。Set-Cookie だけは結合してはいけない。 */':
    '/* Joining repeated names. Set-Cookie is the one that must never be joined. */',
    '/* ---------- 細かい値の読み ---------- */': '/* ---------- Reading the finer values ---------- */',
    '/* 「a=b; c」のような ;区切りのパラメータ。引用符つきの値も戻す。 */':
    '/* Semicolon-separated parameters such as a=b; c. Quoted values are unquoted too. */',
    '/* 「a, b, c」の ,区切り。引用符の中のカンマは割らない。 */':
    '/* Comma-separated lists such as a, b, c. A comma inside quotes does not split. */',
    '/* HTTP-date（RFC 9110 5.6.7）。3つの形を読む。戻り値はミリ秒か null。 */':
    '/* HTTP-date (RFC 9110 5.6.7). Three forms are read. Returns milliseconds, or null. */',

    '/* 桁数が合っていても、存在しない日付は拒む。Date.UTC は 8月32日を黙って9月1日にするので、\n'
    '   組み立て直して同じ年月日に戻るかを見る（Python と突き合わせて見つけた穴）。 */':
    '/* A date that does not exist is rejected even when the digits fit: Date.UTC quietly turns\n'
    '   32 August into 1 September, so we rebuild it and check it returns (found against Python). */',

    '/* 2桁の年は「50年以上先に見えるなら前世紀」と読む決まり（RFC 9110 5.6.7） */':
    '/* A two-digit year more than 50 years ahead belongs to the previous century (RFC 9110 5.6.7) */',
    '/* ---------- ヘッダごとの読み下し ---------- */':
    '/* ---------- Reading each header back in words ---------- */',
    '/* 読み下しを持っているヘッダの一覧。ここに無いものは値をそのまま出す。 */':
    '/* The headers we can read back in words. Anything else has its value shown as is. */',
    '/* ---------- 落とし穴の検出（data-code で機械照合できるようにしてある） ---------- */':
    '/* ---------- Pitfall detection (data-code makes it machine-checkable) ---------- */',
    '/* --- 分解のところ --- */': '/* --- In the parsing --- */',
    '/* --- 要求のとき --- */': '/* --- On a request --- */',
    '/* --- キャッシュ --- */': '/* --- Caching --- */',
    '/* 同じ指摘を Cookie の数だけ並べない。最初の1件だけ出す。 */':
    '/* Do not repeat one finding once per cookie. Report the first only. */',
    '/* --- 中身の種類 --- */': '/* --- The kind of content --- */',
    '/* --- セキュリティの指定 --- */': '/* --- Security directives --- */',
    '/* script-src が無ければ default-src が代わりに効く。style-src だけの unsafe-inline は別の話。 */':
    '/* Without script-src, default-src applies instead. unsafe-inline on style-src alone is another matter. */',
    '/* 新しい書き方は必ず = を持つ。= が1つも無くて空白で区切られていたら古い形。 */':
    '/* The modern syntax always has an =. No = at all and space-separated means the old form. */',
    '/* ---------- キャッシュの寿命（RFC 9111 の式） ---------- */':
    '/* ---------- Cache lifetime (the RFC 9111 formula) ---------- */',
    '/* 10% の端数は切り捨て。規格は丸め方を決めていないので、決めて書いておく。 */':
    '/* The 10% heuristic is floored. The standard does not say how to round, so we say it here. */',
    '/* ---------- 自己検査: ブラウザの Headers と突き合わせる ---------- */':
    '/* ---------- Self-check: compare with the browser Headers class ---------- */',

    '/* 受け付けない文字は、行に組み立て直さず名前と値のまま判定する。\n'
    '     1行にしてから読ませると X:Test が「名前 X、値 Test: v」に割れてしまい、\n'
    '     こちらが拒否できているかを測れない（最初そう書いていた）。 */':
    '/* Rejected characters are judged as a name and a value, not rebuilt into a line.\n'
    '     Rebuilt into one line, X:Test splits into name X and value Test: v, and we can no\n'
    '     longer measure whether we rejected it (this code did that at first). */',

    '/* ---------- 画面 ---------- */': '/* ---------- Screen ---------- */',
    '/* 1行目 */': '/* The first line */',
    '/* 分解した結果 */': '/* What the parse produced */',
    '/* エラー */': '/* Errors */',
    '/* 読み下し */': '/* Read back in words */',
    '/* キャッシュ */': '/* Caching */',
    '/* 指摘 */': '/* Findings */',
}

SITE = "https://hirulab-dev.github.io/hirulab-tools"

TR = {
    # ── 分解のエラー ──────────────────────────────────────────────
    "行頭が空白で始まっていますが、続きにできるヘッダがありません。":
        "This line starts with whitespace, but there is no header above it to continue.",
    "コロンがありません。ヘッダは「名前: 値」の形です。":
        "There is no colon. A header has the form name: value.",
    "名前とコロンの間に空白があります。この形は受け取った側が必ず拒否する決まりです。":
        "There is whitespace between the name and the colon. The recipient is required to reject this.",
    "ヘッダ名に置けない文字が入っています: ":
        "The header name contains a character that is not allowed there: ",
    "値に制御文字が入っています（": "The value contains a control character (at character ",
    "文字目）。": ").",

    # ── 単位 ──────────────────────────────────────────────────────
    "0秒": "0s",
    "秒": "s",
    "分": "m",
    "時間": "h",
    "日": "d",
    " バイト": " bytes",

    # ── Cache-Control の指示 ──────────────────────────────────────
    "この秒数のあいだは新鮮とみなす。過ぎたら元のサーバに確認する":
        "treat as fresh for this many seconds; after that, check with the origin server",
    "共有キャッシュ（CDN・プロキシ）だけに効く寿命。max-age より優先される":
        "a lifetime that only shared caches (CDNs, proxies) honour; it wins over max-age",
    "保存はしてよいが、使う前に毎回元のサーバに確認する（保存しない、ではない）":
        "may be stored, but must be revalidated with the origin server before every use (this is not the same as not storing)",
    "保存してはいけない。ディスクにもメモリにも残さない":
        "must not be stored, on disk or in memory",
    "その利用者だけのもの。共有キャッシュは保存してはいけない":
        "belongs to one user; a shared cache must not store it",
    "ふつうなら保存されない応答でも保存してよい":
        "may be stored even if it would normally not be cacheable",
    "期限が切れたら、元のサーバに繋がらなくても古いものを出してはいけない":
        "once stale, the old copy must not be served even if the origin cannot be reached",
    "must-revalidate と同じことを共有キャッシュにだけ課す":
        "the same as must-revalidate, but only for shared caches",
    "中身を圧縮したり画像を変換したりして渡してはいけない":
        "the payload must not be recompressed or converted on the way",
    "期限内は、再読み込みされても確認しにいかない":
        "while fresh, it is not revalidated even on a reload",
    "この状態コードの保存の決まりを理解できないなら保存しない":
        "do not store unless the caching rules for this status code are understood",
    "期限切れ後この秒数までは、裏で更新しながら古いものを出してよい":
        "for this many seconds after it goes stale, the old copy may be served while refreshing in the background",
    "元のサーバが失敗したら、期限切れ後この秒数までは古いものを出してよい":
        "if the origin fails, the old copy may be served for this many seconds after it goes stale",
    "保存済みのものだけを返す。無ければ取りにいかない":
        "return only what is already stored; do not go and fetch it",
    "この秒数までなら期限切れのものを受け取る":
        "a stale copy is acceptable, up to this many seconds past its lifetime",
    "少なくともこの秒数は新鮮であるものが欲しい":
        "the copy must stay fresh for at least this many seconds",

    # ── SameSite ──────────────────────────────────────────────────
    "別サイトからの遷移では一切送られない": "never sent when arriving from another site",
    "別サイトからでも、リンクをたどる形の移動なら送られる":
        "sent from another site only when following a link as a top-level navigation",
    "別サイトからの読み込みでも送られる（Secure が必須）":
        "sent even on loads from another site (Secure is mandatory)",

    # ── CSP の指令 ────────────────────────────────────────────────
    "下の個別指定が無いときの既定": "the default when no more specific directive is given",
    "スクリプトの取得元": "where scripts may come from",
    "スタイルシートの取得元": "where stylesheets may come from",
    "画像の取得元": "where images may come from",
    "fetch・XHR・WebSocket の接続先": "where fetch, XHR and WebSocket may connect",
    "フォントの取得元": "where fonts may come from",
    "音声・動画の取得元": "where audio and video may come from",
    "プラグインの取得元": "where plugin content may come from",
    "枠に読み込むページの取得元": "where framed pages may come from",
    "ワーカーの取得元": "where workers may come from",
    "このページを枠に入れてよい側": "who may put this page in a frame",
    "base 要素で置ける値": "what the base element may be set to",
    "フォームの送信先": "where forms may be submitted",
    "読み込んだ中身に課す制限": "restrictions placed on the loaded content",
    "http の取得を自動で https に直す": "rewrite http fetches to https automatically",
    "違反の報告先（古い書き方）": "where to report violations (the older spelling)",
    "違反の報告先": "where to report violations",
    "危険な代入に型を要求する": "require a type for dangerous assignments",
    "許す型の名前": "the names of the allowed types",

    # ── Referrer-Policy ───────────────────────────────────────────
    "一切送らない": "never send it",
    "https から http のときだけ送らない": "send it except when going from https to http",
    "オリジンだけ送る（パスは送らない）": "send the origin only (not the path)",
    "別オリジンにはオリジンだけ送る": "send the origin only to other origins",
    "同じオリジンにだけ送る": "send it only to the same origin",
    "オリジンだけ送る。https から http のときは送らない":
        "send the origin only, and nothing when going from https to http",
    "同一オリジンには全部、別オリジンにはオリジンだけ、格下げのときは送らない（既定）":
        "everything to the same origin, the origin only to others, nothing on a downgrade (this is the default)",
    "どこへでもURLを丸ごと送る": "send the whole URL to anyone",

    # ── 状態コード ────────────────────────────────────────────────
    "成功": "success",
    "作成した": "created",
    "成功。本文は無い": "success, with no body",
    "一部だけ返した": "only part of it was returned",
    "恒久的に移動した": "moved permanently",
    "一時的に別の場所にある": "temporarily somewhere else",
    "別の場所を GET で見よ": "look at another place, with GET",
    "変わっていない。保存してあるものを使え": "not modified; use the stored copy",
    "一時的な移動（メソッドを変えない）": "a temporary move, keeping the method",
    "恒久的な移動（メソッドを変えない）": "a permanent move, keeping the method",
    "要求の形がおかしい": "the request is malformed",
    "認証が要る": "authentication is required",
    "許されていない": "not allowed",
    "見つからない": "not found",
    "そのメソッドは使えない": "that method is not available here",
    "いまの状態と食い違う": "it conflicts with the current state",
    "もう無い": "gone for good",
    "本文が大きすぎる": "the body is too large",
    "その形式は受け取れない": "that format cannot be accepted",
    "茶は淹れられない": "cannot brew tea",
    "形は読めたが中身が処理できない": "readable, but the content cannot be processed",
    "要求が多すぎる": "too many requests",
    "サーバ側の失敗": "the server failed",
    "上流から変な返事が来た": "a bad answer came back from upstream",
    "いま扱えない": "cannot handle it right now",
    "上流が時間切れ": "upstream timed out",

    # ── 読み下しの細部 ────────────────────────────────────────────
    "この道具は知らない指示です。受け手はふつう無視します":
        "this page does not know that directive; recipients normally ignore it",
    "（": " (",
    "）": ")",
    "名前": "name",
    "（= がありません。名前だけのCookieは受け取られません）":
        "(there is no =; a cookie with only a name is not accepted)",
    "値": "value",
    "（空）": "(empty)",
    "日付として読めません。読めない Expires は「すでに期限切れ」として扱われます":
        "this is not a readable date; an unreadable Expires counts as already expired",
    "この時刻まで保存される（": "stored until this moment (",
    "0以下なので、このCookieはすぐ削除される":
        "zero or less, so this cookie is deleted immediately",
    "受け取ってから ": "stored for ",
    " 保存される": " after it is received",
    "数字として読めません": "this is not a readable number",
    "このドメインと、その下のサブドメイン全部に送られる":
        "sent to this domain and to every subdomain under it",
    "このパスの下でだけ送られる": "sent only under this path",
    "https のときだけ送られる": "sent only over https",
    "JavaScript からは読めない（document.cookie に出ない）":
        "not readable from JavaScript (it does not appear in document.cookie)",
    "この値は知りません。ブラウザは既定の扱いに落とします":
        "this page does not know that value; browsers fall back to the default",
    "埋め込み先のサイトごとに別のCookieとして扱われる":
        "kept as a separate cookie for each embedding site",
    "数が多すぎて捨てるときの優先度（規格ではなくChromiumの独自指定）":
        "which cookies to drop first when there are too many (a Chromium extension, not a standard)",
    "この道具は知らない属性です。ブラウザはふつう無視します":
        "this page does not know that attribute; browsers normally ignore it",
    "種類": "type",
    "形": "shape",
    "スラッシュがありません。種類として読めない値です":
        "there is no slash, so this is not a readable media type",
    "本文の文字コードは ": "the body is read as ",
    " として読まれる": "",
    "本文をこの区切りで割る": "the body is split on this boundary",
    "この種類の追加指定": "an extra parameter for this media type",
    "この道具は知らない指令です": "this page does not know that directive",
    "0 なので、この設定は解除される": "zero, so this setting is switched off",
    "この秒数のあいだ、http で来ても https に読み替える（":
        "for this many seconds, http requests are rewritten to https (",
    "サブドメイン全部にも同じことを課す": "the same applies to every subdomain",
    "ブラウザに同梱される一覧への収載を希望する（載るかは別の申請と条件しだい）":
        "asks to be included in the list shipped with browsers (whether it gets in depends on a separate submission and its conditions)",
    "この道具は知らない指定です": "this page does not know that setting",
    "HTTPの日付として読めません。読めない日付は「はるか昔」として扱われます":
        "this is not a readable HTTP date; an unreadable date counts as long ago",
    "この端末の時刻で": "in this machine time",
    "いまとの差": "distance from now",
    " 前": " ago",
    " 後": " from now",
    "キャッシュの指示です。左が書いたもの、右がその意味です。":
        "Caching directives. On the left what was written, on the right what it means.",
    "1つのCookieです。ブラウザはこの条件のときだけ送り返します。":
        "One cookie. The browser sends it back only under these conditions.",
    "本文の種類です。ブラウザはこれを見て表示のしかたを決めます。":
        "The type of the body. The browser decides how to present it from this.",
    "読み込んでよい取得元の一覧です。": "The list of sources that may be loaded.",
    "https を強制する設定です。https の応答でだけ効きます。":
        "Forces https. It only takes effect on an https response.",
    "この道具は知らない値です": "this page does not know that value",
    "次のページに、どこから来たかをどれだけ伝えるかです。":
        "How much of where you came from is passed on to the next page.",
    "HTTPの日付です。": "An HTTP date.",
    "本文は ": "the body is ",
    " です": "",
    "本文の長さです。": "The length of the body.",
    "この応答は元のサーバを出てから ": "this response left the origin server ",
    " 経っています（途中のキャッシュに置かれていた時間）":
        " ago (the time it sat in caches along the way)",
    "途中のキャッシュに置かれていた時間です。": "How long it sat in caches along the way.",
    "この応答はキャッシュに保存できない、という意味になる":
        "this means the response cannot be reused from a cache at all",
    "このヘッダの値が違えば別の応答として保存される":
        "a different value of this header is stored as a different response",
    "保存した応答を再利用してよい条件です。":
        "The conditions under which a stored response may be reused.",
    " 待ってから、もう一度試す": " — wait this long, then try again",
    "秒数でも日付でもありません。受け手は無視します":
        "this is neither a number of seconds nor a date; recipients ignore it",
    " 以降に、もう一度試す": " — try again at or after this moment",
    "いつ再挑戦してよいかです。": "When it is all right to try again.",
    "弱い検証子。中身が「実質同じ」なら同じ札にしてよい":
        "a weak validator; the same tag may be used when the content is equivalent enough",
    "強い検証子。1バイトでも違えば別の札になる":
        "a strong validator; one byte of difference means a different tag",
    "中身の版を表す札です。": "A tag standing for this version of the content.",
    "どのページからも枠に入れさせない": "no page at all may put this in a frame",
    "同じオリジンのページからだけ枠に入れてよい":
        "only pages on the same origin may put this in a frame",
    "この書き方はどのブラウザでも動きません（削除済み）":
        "no browser implements this spelling any more (it was removed)",
    "この道具は知らない値です。ブラウザは無視するか DENY として扱います":
        "this page does not know that value; browsers either ignore it or treat it as DENY",
    "このページを枠（iframe）に入れてよいかです。":
        "Whether this page may be put in a frame.",
    "中身を見て種類を推測しない。Content-Type を信じる":
        "do not guess the type from the bytes; trust Content-Type",
    "nosniff 以外の値に意味はありません": "no value other than nosniff means anything",
    "種類の推測をやめさせる指定です。": "Turns off type sniffing.",
    "どのオリジンからでも読める（ただし資格情報つきの要求には使えない）":
        "readable from any origin (but this cannot be used with credentialed requests)",
    "このオリジンからだけ読める。ほかは拒まれる":
        "readable from this origin only; every other one is refused",
    "別オリジンのJavaScriptに中身を読ませてよいかです。":
        "Whether JavaScript on another origin may read the body.",
    "表示せずに保存させる": "save it instead of displaying it",
    "そのまま表示してよい": "it may be displayed as is",
    "保存するときの名前: ": "the name to save it under: ",
    "文字コードつきの名前（RFC 5987）。非ASCIIの名前はこちらで書く":
        "the name with a charset (RFC 5987); non-ASCII names belong here",
    "本文を表示するか保存するかです。": "Whether the body is displayed or saved.",

    # ── 落とし穴 ──────────────────────────────────────────────────
    "名前とコロンの間に空白があります": "There is whitespace between the name and the colon",
    "RFC 9112 は、この形を受け取った側が必ず拒否するよう定めています。応答を2つに割って偽の応答を差し込む古い手口（応答分割）の入口だからです。空白を消してください。":
        "RFC 9112 requires the recipient to reject this. It is the entry point of an old trick that splits one response into two and injects a fake one. Remove the whitespace.",
    "行頭の空白で値を折り返しています": "The value is folded onto the next line with leading whitespace",
    "改行してから空白で続きを書く形（obs-fold）は非推奨で、多くのサーバとプロキシが拒否します。1行に収めてください。":
        "Continuing a value on the next line with leading whitespace (obs-fold) is deprecated, and many servers and proxies reject it. Keep it on one line.",
    "一度しか置けないヘッダが複数あります: ":
        "Headers that may appear only once are duplicated: ",
    "受け手によって、最初を採るか・最後を採るか・カンマで繋いで壊れるかが割れます。1つに絞ってください。":
        "Recipients differ on whether they take the first, take the last, or join them with a comma and break. Keep exactly one.",
    "Set-Cookie が ": "There are ",
    " 個あります": " Set-Cookie headers",
    "Set-Cookie は、同じ名前が複数あってもカンマで結合してはいけない唯一のヘッダです。Expires の値自体にカンマが入っているため、結合すると元に戻せなくなります。1つずつ別の行のまま扱ってください。":
        "Set-Cookie is the one header that must never be joined with a comma, because the value of Expires contains a comma itself, so joining cannot be undone. Keep them on separate lines.",
    "ヘッダの値に ASCII の外の文字が入っています":
        "A header value contains characters outside ASCII",
    "HTTPのヘッダは本来 ASCII の範囲で書くものです。日本語などを直に書くと、受け手によって UTF-8 と読むか Latin-1 と読むかが割れます。ファイル名なら Content-Disposition の filename* を、それ以外なら符号化した形を使ってください。":
        "HTTP headers are meant to stay inside ASCII. Written directly, recipients differ on whether to read the bytes as UTF-8 or as Latin-1. For a file name use filename* in Content-Disposition; otherwise encode the value.",
    "HTTP/1.1 の要求なのに Host がありません": "This is an HTTP/1.1 request with no Host",
    "1.1 では Host は必須で、無い要求はサーバが 400 を返さなければならない決まりです。手で組み立てた要求でよく抜けます。":
        "In 1.1 the Host header is mandatory, and a server is required to answer 400 without it. It goes missing most often in hand-built requests.",
    "Host が複数あります": "There is more than one Host",
    "どれを採るかが実装ごとに割れます。前段と後段で違う Host を採ると、別のサイト宛の要求として通ってしまいます。":
        "Implementations differ on which one to take. When the front and the back take different ones, a request can be routed as if it were meant for another site.",
    "no-cache は「保存しない」ではありません": "no-cache does not mean do not store",
    "保存はされます。使う前に毎回、元のサーバに「変わっていないか」を訊きにいく、という意味です。保存させたくないときは no-store です。":
        "It is stored. It means the cache asks the origin whether it has changed before each use. When you want nothing stored, the directive is no-store.",
    "no-store と寿命の指定が同居しています": "no-store sits next to a lifetime",
    "no-store が勝ちます。max-age や Expires は読まれません。どちらが本当なのかを決めてください。":
        "no-store wins; max-age and Expires are never read. Decide which one you meant.",
    "max-age と Expires の両方があります": "Both max-age and Expires are present",
    "max-age が勝ち、Expires は無視されます。Expires は max-age を理解しない古い相手のためだけに残す形になります。":
        "max-age wins and Expires is ignored. Expires only remains for old recipients that do not understand max-age.",
    "Expires が日付として読めません": "Expires is not a readable date",
    "読めない Expires は「はるか昔の日付」＝すでに期限切れとして扱われます。0 や -1 を書いて「キャッシュさせない」つもりのコードをよく見ますが、狙いどおりに見えるのは偶然です。no-store を使ってください。":
        "An unreadable Expires counts as a date long in the past, so the response is already stale. Code that writes 0 or -1 meaning do not cache is common, and it appears to work only by accident. Use no-store.",
    "Set-Cookie があるのに private も no-store もありません":
        "There is a Set-Cookie but neither private nor no-store",
    "CDN やプロキシがこの応答を保存すると、ある人のCookieが別の人に配られます。個人向けの応答には Cache-Control: private か no-store を付けてください。":
        "If a CDN or a proxy stores this response, one person cookie is handed to another. Personalised responses need Cache-Control: private or no-store.",
    "Vary: * はキャッシュを完全に止めます": "Vary: * stops caching entirely",
    "どんな条件でも再利用してよい保証がない、という意味になります。狙ってやっているなら問題ありませんが、no-store のつもりならそちらを書くほうが伝わります。":
        "It means there is no condition under which the stored response may be reused. That is fine if it is deliberate, but if you meant no-store, writing no-store says so more clearly.",
    "Vary: User-Agent はキャッシュを実質無効にします":
        "Vary: User-Agent makes the cache useless in practice",
    "User-Agent の値は端末ごとにほぼ違うので、保存した応答がまず再利用されません。端末で出し分けたいなら Client Hints か、URL を分ける方法を検討してください。":
        "The User-Agent value differs on almost every device, so a stored response is virtually never reused. To vary by device, look at Client Hints or at separate URLs.",
    "Origin ごとに違う値を返しているのに Vary: Origin がありません":
        "A per-origin value is returned but Vary: Origin is missing",
    "途中のキャッシュが、あるオリジン向けの許可を別のオリジンにも配ります。Access-Control-Allow-Origin を動的に変えるなら Vary: Origin は必須です。":
        "A cache in the middle hands the permission granted to one origin to another one. If Access-Control-Allow-Origin varies, Vary: Origin is mandatory.",
    "Content-Encoding があるのに Vary に Accept-Encoding がありません":
        "There is a Content-Encoding but Accept-Encoding is not in Vary",
    "圧縮した応答が、圧縮を受け取れない相手にそのまま配られることがあります。中身は壊れて見えますが、エラーにはなりません。":
        "A compressed response can be handed to a client that cannot decompress it. The content looks broken, and no error is raised.",
    "Age が max-age を超えています": "Age is larger than max-age",
    "この応答は届いた時点ですでに期限切れです。stale-while-revalidate などで意図的にそうしているのでなければ、途中のキャッシュが古いものを配っています。":
        "This response is already stale on arrival. Unless that is deliberate, through stale-while-revalidate or the like, a cache in the middle is serving something old.",
    "キャッシュの指示がまったくありません": "There is no caching directive at all",
    "この場合キャッシュは Last-Modified からの推測で寿命を決めてよいことになっています（経過時間の10%が広く使われます）。「指定しない＝保存されない」ではありません。":
        "In that case a cache is allowed to guess a lifetime from Last-Modified; 10% of the elapsed time is the widely used guess. Saying nothing does not mean nothing is stored.",
    "immutable は再読み込みでも確認しにいきません":
        "immutable skips revalidation even on a reload",
    "内容が絶対に変わらないURL（名前にハッシュが入ったファイルなど）にだけ付けてください。付けたまま中身を差し替えると、期限が切れるまで古いものが出続けます。":
        "Put it only on URLs whose content can never change, such as files with a hash in the name. Replace the content while it is set, and the old copy keeps being served until the lifetime runs out.",
    "SameSite=None なのに Secure がありません（": "SameSite=None with no Secure (",
    "ブラウザはこのCookieを黙って捨てます。エラーも警告も出ないので、「なぜかログインが維持されない」という形でしか気づけません。":
        "The browser drops this cookie silently. There is no error and no warning, so the only symptom is that the login mysteriously does not stick.",
    "SameSite が指定されていません（": "SameSite is not set (",
    "既定の扱いがブラウザで割れます。Chromium は Lax として扱いますが、そうしないものもあります。書いておくほうが安全です。":
        "Browsers differ on the default. Chromium treats it as Lax; not all of them do. Writing it out is safer.",
    "SameSite の値が読めません（": "The SameSite value is not readable (",
    "Strict / Lax / None のどれでもない値は無視され、既定の扱いに落ちます。綴り違いはここで黙って効かなくなります。":
        "Anything that is not Strict, Lax or None is ignored and falls back to the default. A typo stops working silently right here.",
    "Secure がありません（": "There is no Secure (",
    "http の通信でも送られます。https だけのサイトでも、最初の1回が http なら盗まれます。":
        "It is sent over http as well. Even on an https-only site, one first request over http is enough to leak it.",
    "HttpOnly がありません（": "There is no HttpOnly (",
    "名前からするとセッション用に見えます。HttpOnly が無いと JavaScript から読めるので、スクリプトを1つ差し込まれた時点で持ち出されます。":
        "The name suggests a session cookie. Without HttpOnly it is readable from JavaScript, so one injected script is enough to carry it away.",
    "Domain 指定はサブドメイン全部に広がります（": "A Domain widens it to every subdomain (",
    "Domain=example.com と書くと a.example.com にも b.example.com にも送られます。先頭のドットの有無は関係ありません（RFC 6265 で無視されます）。狭めたいなら Domain を書かないことです。":
        "Domain=example.com means it is sent to a.example.com and b.example.com alike. A leading dot makes no difference; RFC 6265 ignores it. To keep it narrow, leave Domain out.",
    "Max-Age と Expires の両方があります（": "Both Max-Age and Expires are present (",
    "Max-Age が勝ちます。Expires は Max-Age を理解しない相手のためだけに残る形です。":
        "Max-Age wins. Expires only remains for recipients that do not understand Max-Age.",
    "Cookie の値に空白かカンマかセミコロンが入っています（":
        "The cookie value contains a space, a comma or a semicolon (",
    "セミコロンから先は属性として読まれ、値はそこで切れます。値は符号化してから入れてください。":
        "Everything after a semicolon is read as an attribute, and the value is cut off there. Encode the value before putting it in.",
    "Cookie が 4096 バイトを超えています（": "The cookie is larger than 4096 bytes (",
    "、": ", ",
    " バイト）": " bytes)",
    "ブラウザはこの大きさを超えたCookieを保存しません。捨てられたことは通知されません。":
        "Browsers do not store a cookie above that size, and nothing tells you it was dropped.",
    "Content-Type がありません": "There is no Content-Type",
    "ブラウザは本文の先頭を見て種類を推測します。テキストのつもりのものが HTML として実行されることがあります。":
        "The browser guesses the type from the first bytes of the body. Something meant as text can end up running as HTML.",
    "text/ で始まる種類なのに charset がありません":
        "The type starts with text/ but there is no charset",
    "規格上の既定は US-ASCII ですが、実際のブラウザは中身から推測します。UTF-8 のつもりの日本語が化ける典型です。charset=utf-8 と書いてください。":
        "The standard default is US-ASCII, while real browsers guess from the content. This is the classic way UTF-8 text turns into mojibake. Write charset=utf-8.",
    "application/json に charset を付けています": "A charset is attached to application/json",
    "JSON の種類に charset は定義されていないので、受け手は無視します。害はありませんが、これで文字コードが決まると思っていると当てが外れます。JSON は常に UTF-8 です。":
        "The JSON media type defines no charset parameter, so recipients ignore it. It does no harm, but it does not decide the encoding either. JSON is always UTF-8.",
    "X-Content-Type-Options: nosniff がありません": "X-Content-Type-Options: nosniff is missing",
    "ブラウザが Content-Type を信じず、中身から種類を推測することがあります。利用者が上げたファイルを配る場所では特に危険です。":
        "The browser may distrust Content-Type and guess the type from the content. That is especially dangerous where user-uploaded files are served.",
    "filename に ASCII の外の文字を直に書いています":
        "The filename contains characters outside ASCII, written directly",
    "この形は規格に無く、受け手によって化けます。filename*=UTF-8''... の形（RFC 5987）で書き、ASCII だけの filename を併記してください。":
        "No standard covers this form, and recipients garble it differently. Write it as filename*=UTF-8 (RFC 5987) and keep an ASCII-only filename alongside.",
    "Content-Length と Transfer-Encoding が同居しています":
        "Content-Length and Transfer-Encoding sit together",
    "この2つが揃うと、どこで本文が終わるかの判断が受け手ごとに割れます。前段と後段で違う読み方をすると、要求を割り込ませる攻撃（スマグリング）が成立します。Transfer-Encoding があるなら Content-Length は消してください。":
        "With both present, recipients differ on where the body ends. When the front and the back read it differently, a request can be smuggled in between. If Transfer-Encoding is there, drop Content-Length.",
    "X-Frame-Options: ALLOW-FROM はもう効きません":
        "X-Frame-Options: ALLOW-FROM no longer does anything",
    "この書き方に対応しているブラウザはありません。値が読めないので、無視されるか DENY として扱われます。CSP の frame-ancestors を使ってください。":
        "No browser implements this spelling. The value is unreadable, so it is either ignored or treated as DENY. Use frame-ancestors in CSP.",
    "X-Frame-Options と CSP の frame-ancestors が両方あります":
        "Both X-Frame-Options and frame-ancestors in CSP are present",
    "対応しているブラウザでは CSP が勝ち、X-Frame-Options は読まれません。片方だけ直して安心しないでください。":
        "Where CSP is supported it wins, and X-Frame-Options is never read. Fixing only one of them is not enough.",
    "max-age=0 は HSTS の解除です": "max-age=0 switches HSTS off",
    "この応答を受け取ったブラウザは、覚えていた設定を忘れます。止めるときの正しい書き方ですが、意図せず書いてあるなら効き目が消えています。":
        "A browser receiving this forgets what it remembered. That is the correct way to turn it off, but if it is there by accident the protection is simply gone.",
    "preload と書いてありますが条件を満たしていません":
        "preload is written but the conditions are not met",
    "同梱一覧に載るには max-age が 31536000（1年）以上で、includeSubDomains が必要です。条件を外れていてもエラーにはならず、ただ載らないだけです。":
        "To get into the shipped list, max-age must be at least 31536000 (one year) and includeSubDomains must be present. Falling short raises no error; it just never gets in.",
    "CSP が Report-Only でしか出ていません": "CSP is only present as Report-Only",
    "このヘッダは違反を報告するだけで、何も止めません。試すための形なので、そのまま本番に置いたままになっていないか確かめてください。":
        "This header only reports violations; it blocks nothing. It is the form for trying a policy out, so check that it was not left in production as is.",
    "CSP のヘッダが2つあります": "There are two CSP headers",
    "両方が別々に適用され、両方を満たすものだけが通ります。つまり後から足したほうで緩めることはできません。":
        "Both are enforced separately, and only what satisfies both gets through. A second one cannot loosen the first.",
    "スクリプトの取得元に unsafe-inline があります":
        "unsafe-inline is in the source list for scripts",
    "ページに書かれたスクリプトを全部許すという意味なので、CSP の主目的（差し込まれたスクリプトを止めること）がほぼ無くなります。nonce か hash に置き換えてください。":
        "It allows every script written into the page, which removes most of what CSP is for: stopping injected scripts. Replace it with a nonce or a hash.",
    "default-src では代われない指令が抜けています: ":
        "Directives that default-src cannot stand in for are missing: ",
    "この3つは default-src の傘に入りません。書かなければ制限なしです。default-src 'self' を書いたから安心、とはなりません。":
        "These three are not covered by default-src. Left out, they are unrestricted. Writing default-src self is not enough on its own.",
    "Allow-Origin: * と Allow-Credentials: true は同時に使えません":
        "Allow-Origin: * and Allow-Credentials: true cannot be used together",
    "ブラウザはこの組み合わせを拒否します。サーバから見れば200が返っているので、失敗しているのはブラウザの中だけです。資格情報を送るなら、オリジンを具体的に1つ書いてください。":
        "The browser refuses this combination. From the server side a 200 went out, so the failure happens inside the browser only. To send credentials, name exactly one origin.",
    "Allow-Origin にオリジンを複数書いています": "Allow-Origin lists more than one origin",
    "書けるのは1つか * だけです。カンマで並べた値はどのオリジンとも一致しないので、全部拒まれます。要求の Origin を見て1つ選んで返してください。":
        "Only one origin, or *, may be written. A comma-separated value matches no origin at all, so everything is refused. Look at the request Origin and echo one back.",
    "Access-Control-Expose-Headers がありません": "Access-Control-Expose-Headers is missing",
    "別オリジンの JavaScript から読めるのは Cache-Control / Content-Language / Content-Length / Content-Type / Expires / Last-Modified / Pragma の7つだけです。独自ヘッダは、届いていても読めません。":
        "JavaScript on another origin can read only seven headers: Cache-Control, Content-Language, Content-Length, Content-Type, Expires, Last-Modified and Pragma. Your own headers arrive but cannot be read.",
    "Referrer-Policy に unsafe-url があります": "Referrer-Policy contains unsafe-url",
    "クエリ文字列を含むURLを丸ごと外部サイトに送ります。URLにトークンや検索語が入っていると、そのまま渡ります。":
        "The whole URL, query string included, is sent to outside sites. Tokens or search terms in the URL go with it.",
    "Feature-Policy の書き方になっています": "This is written in the Feature-Policy syntax",
    "Permissions-Policy は構造化フィールド（RFC 8941）なので geolocation=() の形で書きます。古い geolocation 'none' の形は読めない値として黙って捨てられます。":
        "Permissions-Policy is a structured field (RFC 8941), so it is written as geolocation=(). The older geolocation none form is discarded silently as an unreadable value.",
    "実装の名前とバージョンを出しています": "The implementation and its version are advertised",
    "攻める側は、まずここを見てから既知の弱点を探します: ":
        "An attacker looks here first and then goes hunting for known weaknesses: ",
    "。消しても守りにはなりませんが、狙いを絞らせる理由もありません。":
        ". Removing it is not a defence in itself, but there is no reason to help narrow the search either.",

    # ── キャッシュの寿命 ──────────────────────────────────────────
    "no-store があるので、どのキャッシュも保存しません。":
        "no-store is present, so no cache stores this.",
    "private があるので、共有キャッシュは保存しません（ブラウザ自身は保存します）。":
        "private is present, so shared caches do not store this (the browser itself does).",
    "Vary: * があるので、保存した応答を再利用できません。":
        "Vary: * is present, so a stored response can never be reused.",
    "読めない Expires": "an Expires that cannot be read",
    "Expires（Date が無いので、いまを基準にしました）":
        "Expires (there is no Date, so now was used as the baseline)",
    "Last-Modified からの推測（経過の10%）":
        "guessed from Last-Modified (10% of the elapsed time)",
    "no-cache があるので、保存はしますが使う前に毎回確認します（実質、寿命は0です）。":
        "no-cache is present, so it is stored but revalidated before every use; the lifetime is effectively zero.",
    "寿命を決める指定がありません。この場合キャッシュは自分の判断で寿命を決めてよいことになっています。":
        "Nothing sets a lifetime. In that case a cache is allowed to decide one for itself.",
    "寿命は ": "The freshness lifetime is ",
    "）。": ").",
    "この応答の齢は ": "The age of this response is ",
    "（Age ": " (Age ",
    " 秒 + Date からの経過 ": "s, plus ",
    " 秒）。": "s since Date).",
    "（Age ヘッダ。Date が無いので経過分は数えていません）。":
        " (from the Age header; there is no Date, so nothing is added for time since then).",
    "immutable があるので、期限内は再読み込みでも確認しにいきません。":
        "immutable is present, so while it is fresh it is not revalidated even on a reload.",
    "must-revalidate があるので、期限切れ後に元のサーバへ繋がらなければエラーを返します（古いものを出しません）。":
        "must-revalidate is present, so once stale, an unreachable origin means an error rather than the old copy.",
    "期限切れ後 ": "For ",
    " までは、裏で更新しながら古いものを出してよいことになっています。":
        " after it goes stale, a cache may serve the old copy while refreshing in the background.",

    # ── 自己検査 ──────────────────────────────────────────────────
    "名前の大文字小文字は区別しない": "header names are case-insensitive",
    "同じ名前はカンマと空白で繋がる": "repeats of a name join with a comma and a space",
    "値の前後の空白は落とされる": "whitespace around the value is dropped",
    "値の中の空白は残る": "whitespace inside the value stays",
    "値の中のタブは残る": "a tab inside the value stays",
    "空の値も置ける": "an empty value is allowed",
    "名前に使える記号（token）": "the punctuation a name may use (token)",
    "3つ以上の重複も順に繋がる": "three or more repeats join in order",
    "値にカンマが入っていてもそのまま": "a comma inside the value is left alone",
    "Cache-Control の値はそのまま持つ": "a Cache-Control value is kept as written",
    "値の 0x80〜0xFF は通る（obs-text）": "bytes 0x80 to 0xFF pass in a value (obs-text)",
    "名前の数字始まりも token なら通る": "a name starting with a digit passes if it is a token",
    "名前に空白は置けない": "a name may not contain a space",
    "名前にコロンは置けない": "a name may not contain a colon",
    "名前に丸括弧は置けない": "a name may not contain parentheses",
    "値に改行は置けない": "a value may not contain a newline",
    "値にヌル文字は置けない": "a value may not contain a null character",
    "ブラウザ側が受け付けませんでした": "the browser refused it",
    ": こちら ": ": ours ",
    " / ブラウザ ": " / browser ",
    "こちらだけが拒否しました": "only this page refused it",
    "こちらだけが拒否": "only this page refuses it",
    "ブラウザだけが拒否": "only the browser refuses it",

    # ── プリセット ────────────────────────────────────────────────
    "よくある応答": "an ordinary response",
    "no-cache のつもり": "meant as do-not-cache",
    "CDNが個人向けを配る形": "a CDN handing out a personalised page",
    "CORS の取り合わせ": "a CORS combination",
    "守りを固めたつもり": "meant to be locked down",
    "ダウンロードさせる": "a download",
    "HTTP/1.1 200 OK\\nContent-Type: application/octet-stream\\nContent-Disposition: attachment; filename=\\\"請求書.pdf\\\"\\nContent-Length: 204800\\nX-Content-Type-Options: nosniff":
        "HTTP/1.1 200 OK\\nContent-Type: application/octet-stream\\nContent-Disposition: attachment; filename=\\\"facture-été.pdf\\\"\\nContent-Length: 204800\\nX-Content-Type-Options: nosniff",
    "形が壊れている": "a malformed block",
    "要求ヘッダ": "request headers",

    # ── 画面まわり ────────────────────────────────────────────────
    "この道具は説明を持っていない状態コードです":
        "this page has no description for that status code",
    "版": "version",
    "状態": "status",
    "理由句": "reason phrase",
    "（無し。理由句に意味はありません）": "(none — the reason phrase carries no meaning)",
    "（表示のためだけの文で、プログラムが見るものではありません）":
        " — text for people to read; programs do not look at it",
    "メソッド": "method",
    "対象": "target",
    " 個目。Set-Cookie は結合しません": " (Set-Cookie headers are never combined)",
    " 個あります。使うときは「": " of them; in use they join as: ",
    "」として繋がります": "",
    " / 書いたのは ": " / written as ",
    "書いたのは ": "written as ",
    "（名前は大文字小文字を区別しません）": " (names are case-insensitive)",
    "空行が出てきたので、そこから先は本文とみなして読んでいません。":
        "A blank line appeared, so everything after it is treated as the body and is not read.",
    "読めなかった行が ": "There are ",
    " 行あります。": " lines that could not be read. The number in front is the line number.",
    "行目: ": ": ",
    "読み下しを持っていないヘッダは、上の表に値だけ出しています。":
        "Headers this page has no reading for appear in the table above with their value only.",
    "共有キャッシュには保存されません。": "A shared cache will not store this.",
    "保存されません。": "This will not be stored.",
    "保存されます。寿命はキャッシュの判断しだいです。":
        "This will be stored. The lifetime is left to the cache.",
    "保存されますが、使う前に毎回確認されます。":
        "This will be stored, but revalidated before every use.",
    "保存されます。新鮮なのは ": "This will be stored. It stays fresh for ",
    "。": ". ",          # 日本語は句点で切れるが、英語は次の文との間に空白が要る（本番で気づいた）
    "いまの齢を引くと、残り ": "Taking off its current age leaves ",
    " です。": ".",
    "齢がそれを超えているので、すでに期限切れです。":
        "Its age is already past that, so it is stale.",
    "CDN やプロキシとして読んでいます（s-maxage と private が効きます）。":
        "Read as a CDN or a proxy, so s-maxage and private apply.",
    "ブラウザ自身のキャッシュとして読んでいます（s-maxage と private は効きません）。":
        "Read as the browser own cache, so s-maxage and private do not apply.",
    "この寿命は規格が決めた値ではなく、広く使われている推測のしかたです。実際の秒数はキャッシュごとに違います。":
        "This lifetime is not fixed by the standard; it is the widely used guess. The real number differs from cache to cache.",
    "この道具の分解を、いまこのブラウザの Headers と突き合わせました: ":
        "Checked the parsing on this page against the Headers object in this browser, right now: ",
    " 一致": " match",
    "。食い違ったところはブラウザのほうが正しいです。":
        ". Where they differ, the browser is right.",
}


def core_of(html):
    return html.split("<script>")[1].split("</script>")[0]


# ── HTML の差し替え ────────────────────────────────────────────────────────
JA_DESC = ("HTTPの応答ヘッダを貼ると、1行ずつ日本語に読み下して、キャッシュがどう効くか・"
           "Cookieが本当に届くか・セキュリティの指定が実際に効いているかを見せる道具です。"
           "no-cache は「保存しない」ではない、SameSite=None なのに Secure が無いと"
           "ブラウザに黙って捨てられる、Content-Encoding があるのに Vary に Accept-Encoding が無い、"
           "といった「エラーにならないので気づけない」ところを名指しします。"
           "ブラウザ内で完結し、データはどこにも送信されません。")
EN_DESC = ("Paste an HTTP response head and this page reads it back line by line: how caching "
           "will actually behave, whether a cookie really reaches the browser, and whether the "
           "security headers are doing anything at all. no-cache does not mean do not store. "
           "SameSite=None without Secure is dropped silently. A Content-Encoding with no "
           "Accept-Encoding in Vary hands compressed bytes to a client that cannot read them. "
           "The traps that raise no error get named. Runs entirely in your browser; nothing is uploaded.")
JA_TITLE = "HTTPヘッダの読み下し — エラーにならない設定ミスを名指しする"
EN_TITLE = "HTTP Header Explainer — naming the mistakes that raise no error"
JA_SHORT = ("応答ヘッダを貼ると1行ずつ日本語に読み下し、キャッシュの寿命・Cookieが本当に届くか・"
            "セキュリティの指定が効いているかを見せます。no-cache は保存しないという意味ではない、"
            "SameSite=None に Secure が無いと黙って捨てられる。エラーにならない落とし穴を名指しします。")
EN_SHORT = ("Paste a response head and it is read back line by line: the freshness lifetime, whether "
            "a cookie really arrives, and whether the security headers do anything. no-cache does not "
            "mean do not store. SameSite=None without Secure is dropped silently. The traps that raise "
            "no error get named.")

JA_LD_DESC = ("HTTPの応答ヘッダを貼ると、1行ずつ日本語に読み下して、キャッシュがどう効くか・"
              "Cookieが本当に届くか・セキュリティの指定が実際に効いているかを見せる道具です。"
              "no-cache は保存しないという意味ではない、SameSite=None なのに Secure が無いと"
              "ブラウザに黙って捨てられる、Content-Encoding があるのに Vary に Accept-Encoding が無い、"
              "といったエラーにならない落とし穴を名指しします。ブラウザ内で完結します。")

HTML_PARTS = [
 ('<html lang="ja">', '<html lang="en">'),
 ('<title>%s</title>' % JA_TITLE, '<title>%s</title>' % EN_TITLE),
 ('<meta name="description" content="%s">' % JA_DESC,
  '<meta name="description" content="%s">' % EN_DESC),
 ('<link rel="canonical" href="%s/headers/">' % SITE,
  '<link rel="canonical" href="%s/en/headers.html">' % SITE),
 ('<meta property="og:locale" content="ja_JP">', '<meta property="og:locale" content="en_US">'),
 ('<meta property="og:site_name" content="クロードの昼ラボ">',
  '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">'),
 ('<meta property="og:title" content="%s">' % JA_TITLE,
  '<meta property="og:title" content="%s">' % EN_TITLE),
 ('<meta property="og:description" content="%s">' % JA_SHORT,
  '<meta property="og:description" content="%s">' % EN_SHORT),
 ('<meta property="og:url" content="%s/headers/">' % SITE,
  '<meta property="og:url" content="%s/en/headers.html">' % SITE),
 ('<meta property="og:image" content="%s/ogp/ogp-headers.png">' % SITE,
  '<meta property="og:image" content="%s/ogp/ogp-headers-en.png">' % SITE),
 ('<meta name="twitter:title" content="%s">' % JA_TITLE,
  '<meta name="twitter:title" content="%s">' % EN_TITLE),
 ('<meta name="twitter:description" content="応答ヘッダを貼ると1行ずつ読み下し、キャッシュの寿命・Cookieの届き方・セキュリティ指定の効き目を見せます。エラーにならない落とし穴を名指しします。ブラウザ内で完結します。">',
  '<meta name="twitter:description" content="Paste a response head and it is read back line by line: freshness lifetime, whether cookies arrive, whether the security headers work. The traps that raise no error get named. Runs entirely in your browser.">'),
 ('<meta name="twitter:image" content="%s/ogp/ogp-headers.png">' % SITE,
  '<meta name="twitter:image" content="%s/ogp/ogp-headers-en.png">' % SITE),
 ('  "name": "HTTPヘッダの読み下し",\n  "url": "%s/headers/",' % SITE,
  '  "name": "HTTP Header Explainer",\n  "url": "%s/en/headers.html",' % SITE),
 ('  "description": "%s",' % JA_LD_DESC, '  "description": "%s",' % EN_DESC),
 ('  "browserRequirements": "JavaScript が有効なモダンブラウザ",',
  '  "browserRequirements": "A modern browser with JavaScript enabled",'),
 ('  "inLanguage": "ja",', '  "inLanguage": "en",'),
 ('  "image": "%s/ogp/ogp-headers.png",' % SITE,
  '  "image": "%s/ogp/ogp-headers-en.png",' % SITE),
 ('  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },\n  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "%s/" }' % SITE,
  '  "author": { "@type": "Organization", "name": "Claude\'s Daytime Lab", "url": "https://note.com/hirulab" },\n  "isPartOf": { "@type": "WebSite", "name": "Claude\'s Daytime Lab — tools", "url": "%s/en/" }' % SITE),

 ('  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>\n  <h1>HTTPヘッダの読み下し</h1>',
  '  <a class="hl-back" href="./">← Claude&#39;s Daytime Lab tools</a>\n  <h1>HTTP Header Explainer</h1>'),

 ('''  <p class="lead">応答ヘッダを貼ると、<strong>1行ずつ日本語に読み下して、実際に何が起きるか</strong>を見せる道具です。
    HTTPヘッダは<strong>書き間違えてもエラーが出ません</strong>。
    <code>SameSite=None</code> に <code>Secure</code> を付け忘れたCookieは、
    警告もなくブラウザに捨てられます。この道具は、そういうところを名指しします。</p>''',
  '''  <p class="lead">Paste a response head and this page reads it back <strong>line by line, saying
    what will actually happen</strong>. HTTP headers <strong>raise no error when you get them
    wrong</strong>. A cookie with <code>SameSite=None</code> and no <code>Secure</code> is dropped
    by the browser without a word. This page names those places.</p>'''),

 ('''  <div class="privacy">
    <strong>このページは通信を一切行いません。</strong>
    解析はすべてブラウザの中でやっています。読み込んだあとは機内モードでも動きます。
    貼り付けたヘッダ（<code>Set-Cookie</code> のセッションIDや <code>Authorization</code> を含みます）が
    どこかに送られることはありません。<strong>書かれているURLを開きにいくこともありません。</strong>
  </div>''',
  '''  <div class="privacy">
    <strong>This page makes no network requests.</strong>
    All parsing happens in your browser; once loaded it works offline.
    Nothing you paste — the session id in a <code>Set-Cookie</code>, an <code>Authorization</code>
    header — is sent anywhere. <strong>URLs in the headers are never fetched either.</strong>
  </div>'''),

 ('    <label for="src" class="hide">HTTPヘッダ</label>',
  '    <label for="src" class="hide">HTTP headers</label>'),
 ('      <label><input type="checkbox" id="shared" checked> 共有キャッシュ（CDN・プロキシ）として読む</label>',
  '      <label><input type="checkbox" id="shared" checked> read it as a shared cache (CDN, proxy)</label>'),
 ('    <h2>1行目</h2>', '    <h2>The first line</h2>'),
 ('    <h2>分解した結果</h2>', '    <h2>The fields</h2>'),
 ('        <thead><tr><th>ヘッダ名</th><th>値</th><th>備考</th></tr></thead>',
  '        <thead><tr><th>header</th><th>value</th><th>notes</th></tr></thead>'),
 ('    <h2>1つずつ読み下す</h2>', '    <h2>Read back, one at a time</h2>'),
 ('    <h2>キャッシュはどうなるか</h2>', '    <h2>What caching will do</h2>'),
 ('    <h2>気をつけるところ</h2>', '    <h2>Things to watch out for</h2>'),
 ('    <p class="none" id="notesNone">いまのところ指摘はありません。</p>',
  '    <p class="none" id="notesNone">Nothing to flag right now.</p>'),
 ('    <h2>自己検査</h2>', '    <h2>Self-check</h2>'),

 ('''    <summary>この道具は何を自分で計算しているのか</summary>
    <ul>
      <li><b>ヘッダの分解はブラウザの <code>Headers</code> を使わず、自分で書いています。</b>
        RFC 9110 / 9112 の決まり（名前に置ける文字、値の前後の空白の落とし方、
        同じ名前が複数回来たときの結合、行頭空白での折り返し）をなぞった実装です。</li>
      <li><b>キャッシュの寿命は RFC 9111 の式で計算しています。</b>
        <code>s-maxage</code> → <code>max-age</code> → <code>Expires</code> − <code>Date</code> の順に見て、
        どれも無ければ <code>Last-Modified</code> からの推測（経過時間の10%）を使います。
        <b>齢</b>は <code>Age</code> と <code>Date</code> から出します。</li>
      <li>自前である以上ずれる可能性があります。だから<b>毎回その場でブラウザの
        <code>Headers</code> と突き合わせ、結果を自己検査の欄に出しています</b>。
        名前の正規化・値の前後の空白・結合のしかた・受け付けない文字の4点を見ています。</li>
      <li><b>できていないところも書いておきます。</b>
        <code>Content-Security-Policy</code> は指令ごとの値を並べて読むだけで、
        個々のURLがそのポリシーで通るかどうかまでは判定しません。
        構造化フィールド（RFC 8941）も、辞書とリストの形だけを見ています。</li>
      <li>ヘッダの値そのものは<b>1バイトも書き換えません</b>。読み下しは別の欄に出します。</li>
    </ul>''',
  '''    <summary>What this page computes for itself</summary>
    <ul>
      <li><b>The parsing does not use the browser <code>Headers</code> object; it is written here.</b>
        It follows RFC 9110 and 9112: which characters a name may contain, how whitespace around a
        value is dropped, how repeats of one name are joined, and folding with leading whitespace.</li>
      <li><b>The freshness lifetime is computed with the formula in RFC 9111.</b>
        It looks at <code>s-maxage</code>, then <code>max-age</code>, then
        <code>Expires</code> − <code>Date</code>, and if none of those are there it falls back to a
        guess from <code>Last-Modified</code> (10% of the elapsed time).
        <b>Age</b> comes from <code>Age</code> plus the time since <code>Date</code>.</li>
      <li>Written by hand, it can drift. So <b>it is checked against this browser
        <code>Headers</code> object every time the page loads</b>, and the result is printed in the
        self-check panel: name normalisation, whitespace around values, how repeats join, and which
        characters are refused.</li>
      <li><b>What it does not do, said plainly.</b>
        <code>Content-Security-Policy</code> is only listed directive by directive; this page does
        not decide whether a given URL would pass the policy.
        Structured fields (RFC 8941) are read only as far as their dictionary and list shapes.</li>
      <li>The header values themselves are <b>never rewritten, not by one byte</b>. The reading is
        shown in a separate column.</li>
    </ul>'''),

 ('''  <footer>
    作ったのは「クロードの昼ラボ」（AIのClaude）です。使用は無料・登録不要。
    読み方は RFC 9110・9111・9112（HTTPの本体とキャッシュ）と RFC 6265（Cookie）に合わせています。
    ブラウザやCDNは規格に無い独自の判断を足すことがあり、
    <b>その食い違い自体が事故のもと</b>です。指摘欄ではそこも書いています。
  </footer>''',
  '''  <footer>
    Built by Claude&#39;s Daytime Lab (Claude, an AI). Free to use, no sign-up.
    The reading follows RFC 9110, 9111 and 9112 (HTTP itself and caching) and RFC 6265 (cookies).
    Browsers and CDNs add judgements of their own that no standard covers, and
    <b>that gap is itself a source of accidents</b>. The notes say where.
  </footer>'''),
]


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "headers" / "index.html"
    en_path = docs / "en" / "headers.html"
    ja = ja_path.read_text(encoding="utf-8")

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit("HTMLの差し替え元が見つかりません:\n" + a[:200])
        en = en.replace(a, b, 1)
    # ナビは日本語版の一覧をまるごと英語版のものに差し替える
    ja_nav = re.search(r'  <nav class="hl-nav">.*?\n  </nav>', en, re.S)
    if not ja_nav:
        sys.exit("ナビが見つかりません")
    en = en[:ja_nav.start()] + EN_NAV + en[ja_nav.end():]

    for a, b in sorted(TR.items(), key=lambda kv: -len(kv[0])):
        en = en.replace('"' + a + '"', '"' + b + '"')

    # 画面に出るところに日本語が残っていないか。
    # 仮名・漢字だけ見ていると約物（、。「」（））が素通りするので、そこも見る。
    body = re.sub(r"/\*.*?\*/", "", en, flags=re.S)
    body = re.sub(r"(?m)(?<!:)//.*$", "", body)
    left = re.findall("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？]+", body)
    if left:
        sys.exit("日本語が %d 箇所残っています: %s" % (len(left), left[:12]))

    a, b = blank(core_of(ja)), blank(core_of(en))
    if a != b:
        for k, (x, y) in enumerate(zip(a.split("\n"), b.split("\n"))):
            if x != y:
                sys.exit("コードが一致しません（%d行目）:\n  ja: %s\n  en: %s" % (k + 1, x, y))
        sys.exit("コードの行数が違います（ja %d / en %d）" % (a.count("\n"), b.count("\n")))

    # ★2026-09-03 夜: JS のコメントも訳す
    s0 = en.index("<script>") + len("<script>")
    e0 = en.index("</script>", s0)
    core_en, missing = translate_comments(en[s0:e0], COMMENTS)
    if missing:
        sys.exit("訳されていないコメントが %d 件あります:\n  %s"
                 % (len(missing), "\n  ".join(x[:100] for x in missing[:8])))
    left_c = re.findall("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？]+",
                        "\n".join(comments(core_en)))
    if left_c:
        sys.exit("コメントに日本語が %d 箇所残っています: %s" % (len(left_c), left_c[:12]))
    en = en[:s0] + core_en + en[e0:]

    en_path.parent.mkdir(parents=True, exist_ok=True)
    # ★2026-09-03 夜: CSS のコメントも訳す(<script> の外なので、それまで誰も見ていなかった)
    en, css_missing = translate_css_comments(en)
    if css_missing:
        sys.exit("訳されていない CSS のコメントが %d 件あります:\n  %s"
                 % (len(css_missing), "\n  ".join(x[:100] for x in css_missing[:8])))

    en_path.write_text(en, encoding="utf-8", newline="\n")
    print("書き出した: %s" % en_path)
    print("日本語の残り: 0箇所")
    print("文字列の中身を空にしたコード: 日英でバイト単位で一致（%d バイト）" % len(a.encode()))


EN_NAV = '''  <nav class="hl-nav">
    <h2>Other tools</h2>
    <ul>
      <li><a href="./regex-why.html">Why doesn&#39;t my regex match?</a></li>
      <li><a href="./replace.html">Regex Replacement Preview</a></li>
      <li><a href="./railroad.html">Regex Railroad Diagrams</a></li>
      <li><a href="./regex-tester.html">Regex Tester</a></li>
      <li><a href="./char-counter.html">Character Counter</a></li>
      <li><a href="./palette.html">Color Palette Generator</a></li>
      <li><a href="./timezone.html">Time Zone Converter</a></li>
      <li><a href="./csv.html">CSV Preview &amp; Diagnostics</a></li>
      <li><a href="./url.html">URL Parser &amp; Builder</a></li>
      <li><a href="./jwt.html">JWT Explainer</a></li>
      <li><a href="./password.html">Password Generator &amp; Strength Check</a></li>
      <li><a href="./base64.html">Base64 &amp; Data URL Explainer</a></li>
      <li><a href="./qr.html">QR Code Generator</a></li>
      <li><a href="./cron.html">Cron Expression Explainer</a></li>
      <li><a href="./contrast.html">Contrast Ratio Checker</a></li>
      <li><a href="./image.html">Image Resizer &amp; Compressor</a></li>
      <li><a href="./page-contrast.html">Whole-Page Contrast Audit</a></li>
      <li><a href="./diff.html">Text Diff</a></li>
      <li><a href="./json.html">JSON Formatter &amp; Validator</a></li>
      <li><a href="./unit.html">Unit Converter</a></li>
      <li><a href="./pattern.html">Japanese Pattern Generator</a></li>
      <li><a href="./date.html">Japanese Date Calculator</a></li>
      <li><a href="./take-home.html">Japan Take-Home Pay Calculator</a></li>
      <li><a href="./frima-profit.html">Flea-Market Profit Calculator</a></li>
      <li><a href="../headers/">Japanese version</a></li>
    </ul>
    <p class="hl-links">
      <a href="./">Tools index</a> ·
      <a href="https://note.com/hirulab">Experiment log (JP)</a> ·
      <a href="https://x.com/hirulab_ai">X</a> ·
      <a href="https://github.com/hirulab-dev/hirulab-tools">Source</a>
    </p>
  </nav>'''


if __name__ == "__main__":
    main()
