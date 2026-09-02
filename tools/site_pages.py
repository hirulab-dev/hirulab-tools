#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公開サイトのページ一覧を「手で書いたリスト」ではなく docs/ を舐めて作る。

なぜこれが要るか(2026-08-22 の反省):
  検査スクリプトの対象を配列で持っていたせいで、**後から足したページが検査から漏れる**
  事故を3回起こした(8/21 の英語トップ、8/22 の en/ 3本、同日のリンク色)。
  「作ったら足す」は必ず忘れる。ディレクトリを走査すれば忘れようがない。

ページの鍵(key)の決め方:
  docs/index.html          -> ""                  (トップ)
  docs/qr/index.html       -> "qr/"               (ディレクトリ形式)
  docs/en/timezone.html    -> "en/timezone.html"  (ファイル形式)
この鍵に BASE を足せば本番URL、docs ディレクトリを足せばローカルのパスになる。
"""
import posixpath
from pathlib import Path
from urllib.parse import urldefrag, urlparse

SITE = "https://hirulab-dev.github.io/hirulab-tools/"
OWN_HOSTS = {"hirulab-dev.github.io"}


def discover(docs_dir):
    """docs/ 以下の *.html を全部拾って鍵の一覧を返す(トップが先頭、あとは名前順)。"""
    docs = Path(docs_dir)
    keys = []
    for p in sorted(docs.rglob("*.html")):
        rel = p.relative_to(docs).as_posix()
        if rel == "index.html":
            keys.append("")
        elif rel.endswith("/index.html"):
            keys.append(rel[: -len("index.html")])
        else:
            keys.append(rel)
    keys.sort(key=lambda k: (k != "", k))
    return keys


def key_to_file(docs_dir, key):
    """鍵 -> ローカルのファイルパス。"""
    rel = (key + "index.html") if (key == "" or key.endswith("/")) else key
    return Path(docs_dir) / rel


def key_to_url(base, key):
    """鍵 -> URL。base はサイトの根(末尾スラッシュつき)。file:// でも動く。"""
    if base.startswith("file://"):
        rel = (key + "index.html") if (key == "" or key.endswith("/")) else key
        return base + rel
    return base + key


def resolve(current_key, href):
    """あるページの中の href を、サイト内の鍵に正規化する。

    返り値 (種別, 値):
      ("page",     鍵)        サイト内のページを指している
      ("asset",    相対パス)   サイト内のページ以外(画像・xml 等)
      ("external", URL)       外部
      ("skip",     理由)      #だけ・mailto: など、たどらないもの
    """
    href = (href or "").strip()
    if not href or href.startswith("#"):
        return ("skip", "同一ページ内")
    if href.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return ("skip", href.split(":", 1)[0])

    u = urlparse(href)
    if u.scheme in ("http", "https"):
        if u.hostname not in OWN_HOSTS:
            return ("external", href)
        # 自サイトの絶対URL。サイトの根より下だけを鍵にする
        root = urlparse(SITE).path            # /hirulab-tools/
        if not u.path.startswith(root):
            return ("asset", u.path)
        href = u.path[len(root):]
        current_key = ""                       # 絶対パスなので根から解決する
    elif href.startswith("/"):
        root = urlparse(SITE).path
        if not href.startswith(root):
            return ("asset", href)
        href = href[len(root):]
        current_key = ""

    href = urldefrag(href)[0].split("?")[0]
    if href == "":
        return ("skip", "同一ページ内")

    cur_dir = posixpath.dirname(current_key.rstrip("/") if current_key.endswith("/")
                                else current_key)
    if current_key.endswith("/") or current_key == "":
        cur_dir = current_key                  # ディレクトリ形式のページは自分がディレクトリ
    target = posixpath.normpath(posixpath.join(cur_dir, href))
    if target == ".":
        target = ""
    if href.endswith("/") and target != "":
        target += "/"

    if target.endswith("index.html"):
        target = target[: -len("index.html")]
    if target.endswith(".html") or target == "" or target.endswith("/"):
        return ("page", target)
    return ("asset", target)
