from __future__ import annotations

import html
import re
from urllib.parse import urlparse

FORMAT_TOKENS: list[tuple[str, str]] = [
    ("||", "tg-spoiler"),
    ("__", "u"),
    ("*", "b"),
    ("_", "i"),
    ("~", "s"),
]
LANGUAGE_HINT_PATTERN = re.compile(r"^[A-Za-z0-9_+.-]+$")


def render_user_content(value: str) -> str:
    rendered, _ = _render_segment(value, 0, None)
    return rendered


def _render_segment(value: str, index: int, stop_token: str | None) -> tuple[str, int]:
    parts: list[str] = []

    while index < len(value):
        if stop_token and value.startswith(stop_token, index):
            return "".join(parts), index + len(stop_token)

        if _is_line_start(value, index) and value.startswith(">", index):
            rendered, new_index = _render_blockquote(value, index)
            parts.append(rendered)
            index = new_index
            continue

        if value.startswith("\\", index):
            if index + 1 < len(value):
                parts.append(html.escape(value[index + 1]))
                index += 2
            else:
                parts.append("\\")
                index += 1
            continue

        if value.startswith("```", index):
            rendered, new_index = _render_code_block(value, index)
            parts.append(rendered)
            index = new_index
            continue

        if value.startswith("`", index):
            rendered, new_index = _render_inline_code(value, index)
            parts.append(rendered)
            index = new_index
            continue

        if value.startswith("[", index):
            rendered, new_index = _render_link(value, index)
            if new_index != index:
                parts.append(rendered)
                index = new_index
                continue

        matched_token = False
        for token, tag in FORMAT_TOKENS:
            if value.startswith(token, index):
                rendered, new_index = _render_format(value, index, token, tag)
                if new_index != index:
                    parts.append(rendered)
                    index = new_index
                    matched_token = True
                    break
        if matched_token:
            continue

        parts.append(html.escape(value[index]))
        index += 1

    return "".join(parts), index


def _render_blockquote(value: str, index: int) -> tuple[str, int]:
    quote_lines: list[str] = []
    cursor = index

    while cursor < len(value) and _is_line_start(value, cursor) and value.startswith(">", cursor):
        cursor += 1
        if cursor < len(value) and value[cursor] == " ":
            cursor += 1

        line_end = value.find("\n", cursor)
        if line_end == -1:
            quote_lines.append(value[cursor:])
            cursor = len(value)
            break

        quote_lines.append(value[cursor:line_end])
        next_line_start = line_end + 1
        if next_line_start < len(value) and value.startswith(">", next_line_start):
            cursor = next_line_start
            continue

        cursor = line_end
        break

    inner, _ = _render_segment("\n".join(quote_lines), 0, None)
    return f"<blockquote>{inner}</blockquote>", cursor


def _render_code_block(value: str, index: int) -> tuple[str, int]:
    end = _find_unescaped(value, "```", index + 3)
    if end == -1:
        return html.escape(value[index]), index + 1

    raw_body = value[index + 3 : end]
    code_body = raw_body
    if "\n" in raw_body:
        first_line, remainder = raw_body.split("\n", 1)
        if first_line and LANGUAGE_HINT_PATTERN.fullmatch(first_line.strip()):
            code_body = remainder

    code = html.escape(code_body.strip("\n"))
    return f"<pre><code>{code}</code></pre>", end + 3


def _render_inline_code(value: str, index: int) -> tuple[str, int]:
    end = _find_unescaped(value, "`", index + 1)
    if end == -1:
        return html.escape(value[index]), index + 1

    code = html.escape(value[index + 1 : end])
    return f"<code>{code}</code>", end + 1


def _render_link(value: str, index: int) -> tuple[str, int]:
    label, label_end = _render_segment(value, index + 1, "]")
    if label_end <= index + 1 or label_end >= len(value) or value[label_end] != "(":
        return html.escape(value[index]), index + 1

    url_end = _find_link_url_end(value, label_end)
    if url_end == -1:
        return html.escape(value[index]), index + 1

    url = value[label_end + 1 : url_end].strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return html.escape(value[index]), index + 1

    safe_url = html.escape(url, quote=True)
    return f'<a href="{safe_url}">{label}</a>', url_end + 1


def _render_format(value: str, index: int, token: str, tag: str) -> tuple[str, int]:
    end = _find_unescaped(value, token, index + len(token))
    if end == -1:
        return html.escape(token), index + len(token)

    inner, _ = _render_segment(value, index + len(token), token)
    if not inner:
        return html.escape(token), index + len(token)

    return f"<{tag}>{inner}</{tag}>", end + len(token)


def _find_unescaped(value: str, token: str, start: int) -> int:
    index = start
    while index < len(value):
        if value.startswith("\\", index):
            index += 2
            continue
        if value.startswith(token, index):
            return index
        index += 1
    return -1


def _find_link_url_end(value: str, open_paren_index: int) -> int:
    if open_paren_index >= len(value) or value[open_paren_index] != "(":
        return -1

    depth = 1
    index = open_paren_index + 1
    while index < len(value):
        if value.startswith("\\", index):
            index += 2
            continue
        if value[index] == "(":
            depth += 1
        elif value[index] == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def _is_line_start(value: str, index: int) -> bool:
    return index == 0 or value[index - 1] == "\n"
