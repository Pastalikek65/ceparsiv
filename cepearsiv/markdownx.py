from html import escape
from typing import Any

from markdown_it import MarkdownIt

_ALLOWED_SCHEMES = {"http", "https", "mailto", "ftp"}


def _safe_href(href: str) -> str:
    cleaned = href.strip()
    if cleaned.startswith(("#", "/")):
        return cleaned
    if ":" not in cleaned:
        return cleaned
    scheme = cleaned.split(":", 1)[0].lower()
    if scheme in _ALLOWED_SCHEMES:
        return cleaned
    return "#"


def _link_open(self: Any, tokens: Any, idx: int, options: Any, env: Any) -> str:
    token = tokens[idx]
    href = _safe_href(token.attrGet("href") or "")
    title = token.attrGet("title")
    parts = [f'href="{escape(href, quote=True)}"']
    if title:
        parts.append(f'title="{escape(title, quote=True)}"')
    parts.append('rel="nofollow noopener"')
    return "<a " + " ".join(parts) + ">"


_md = MarkdownIt("commonmark")
_md.options["html"] = False
_md.add_render_rule("link_open", _link_open)


def render_markdown(text: str | None) -> str:
    if not text:
        return ""
    return _md.render(text)
