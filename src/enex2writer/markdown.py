"""ENML/HTML fragment to Markdown rendering with no external dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import re
from typing import Callable
from urllib.parse import quote


@dataclass(slots=True)
class AssetReference:
    """The Markdown-facing location and type of an extracted resource."""

    relative_path: str
    display_name: str
    is_image: bool


@dataclass(slots=True)
class _Node:
    tag: str | None
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["_Node"] = field(default_factory=list)
    data: str = ""


class _FragmentParser(HTMLParser):
    """Build a tolerant tree from the HTML-like ENML body."""

    _VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "en-media",
        "en-todo",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node(None)
        self._stack = [self.root]

    def _add_element(self, tag: str, attrs: list[tuple[str, str | None]]) -> _Node:
        node = _Node(tag.casefold(), {key.casefold(): value or "" for key, value in attrs})
        self._stack[-1].children.append(node)
        return node

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = self._add_element(tag, attrs)
        if node.tag not in self._VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._add_element(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        wanted = tag.casefold()
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == wanted:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(_Node(None, data=data))

    def handle_comment(self, _data: str) -> None:
        # Evernote comments are implementation details rather than note text.
        return

    def handle_decl(self, _decl: str) -> None:
        return


def _strip_enml_prolog(content: str) -> str:
    """Remove XML/doctype wrappers that HTMLParser should not see as content."""

    content = re.sub(r"^\s*<\?xml[^>]*\?>", "", content, count=1, flags=re.I | re.S)
    content = re.sub(r"<!doctype[^>]*>", "", content, count=1, flags=re.I | re.S)
    return content


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value)


def _normalise_title(value: str) -> str:
    return _collapse_whitespace(value).strip().casefold()


class MarkdownRenderer:
    """Render one ENML body and delegate resource/link decisions to callers."""

    _BLOCK_TAGS = {
        "address",
        "article",
        "dd",
        "details",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "footer",
        "header",
        "main",
        "nav",
        "p",
        "section",
        "summary",
    }
    _INLINE_FORMATTING = {
        "b": "**",
        "del": "~~",
        "em": "*",
        "i": "*",
        "s": "~~",
        "strike": "~~",
        "strong": "**",
    }

    def __init__(
        self,
        resource_resolver: Callable[[dict[str, str]], AssetReference | None] | None = None,
        link_resolver: Callable[[str, str], str] | None = None,
    ) -> None:
        self.resource_resolver = resource_resolver or (lambda _attrs: None)
        self.link_resolver = link_resolver or (lambda href, _label: href)

    def render(self, content: str) -> str:
        parser = _FragmentParser()
        parser.feed(_strip_enml_prolog(content))
        parser.close()
        return self._clean_document(self._render_children(parser.root))

    def _render_children(self, node: _Node, *, inline: bool = False, preformatted: bool = False) -> str:
        return "".join(self._render(child, inline=inline, preformatted=preformatted) for child in node.children)

    def _render(self, node: _Node, *, inline: bool = False, preformatted: bool = False) -> str:
        if node.tag is None:
            if preformatted:
                return node.data
            if not node.data.strip():
                # Newline indentation between block-level ENML elements is
                # layout, while a literal single-space node between inline
                # elements still separates words.
                return "" if "\n" in node.data or "\r" in node.data else " "
            return _collapse_whitespace(node.data)

        tag = node.tag
        if tag in {"en-note", "html", "body"}:
            return self._render_children(node, inline=inline, preformatted=preformatted)
        if tag in {"script", "style", "title"}:
            return ""
        if tag == "en-media":
            return self._render_resource(node.attrs)
        if tag == "en-todo":
            checked = node.attrs.get("checked", "").casefold() in {"true", "1", "yes"}
            return "[x] " if checked else "[ ] "
        if tag == "br":
            return "\n"
        if tag == "hr":
            return "\n\n---\n\n"
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            inner = self._render_children(node, inline=True).strip()
            if not inner:
                return ""
            level = int(tag[1])
            return f"\n\n{'#' * level} {inner}\n\n"
        if tag in {"ul", "ol"}:
            return self._render_list(node, depth=0)
        if tag == "li":
            return self._render_children(node)
        if tag == "blockquote":
            inner = self._render_children(node).strip()
            if not inner:
                return ""
            quoted = "\n".join(f"> {line}" if line else ">" for line in inner.splitlines())
            return f"\n\n{quoted}\n\n"
        if tag == "pre":
            return self._render_pre(node)
        if tag == "table":
            return self._render_table(node)
        if tag == "a":
            return self._render_link(node)
        if tag == "img":
            source = node.attrs.get("src", "")
            if not source:
                return ""
            alt = node.attrs.get("alt", "image") or "image"
            return f"![{alt}]({self._link_destination(source)})"
        if tag in self._INLINE_FORMATTING:
            inner = self._render_children(node, inline=True)
            if not inner.strip():
                return ""
            marker = self._INLINE_FORMATTING[tag]
            return f"{marker}{inner.strip()}{marker}"
        if tag == "code":
            inner = self._render_children(node, inline=True).strip()
            if not inner:
                return ""
            marker = "``" if "`" in inner else "`"
            return f"{marker}{inner}{marker}"
        if tag in {"sup", "sub"}:
            inner = self._render_children(node, inline=True).strip()
            return f"<{tag}>{inner}</{tag}>" if inner else ""
        if tag in self._BLOCK_TAGS:
            if inline:
                return self._render_children(node, inline=True, preformatted=preformatted)
            inner = self._render_children(node, preformatted=preformatted).strip()
            return f"\n\n{inner}\n\n" if inner else ""

        # ENML contains a number of harmless formatting/container elements
        # (span, font, en-crypt, and custom tags). Their text and supported
        # descendants are safer to keep than to discard.
        return self._render_children(node, inline=inline, preformatted=preformatted)

    def _render_resource(self, attrs: dict[str, str]) -> str:
        reference = self.resource_resolver(attrs)
        if reference is None:
            identifier = attrs.get("hash") or attrs.get("resource-id") or "unknown"
            return f"[Missing Evernote attachment: {identifier}]"
        destination = quote(reference.relative_path, safe="/-._~")
        if reference.is_image:
            return f"![{reference.display_name}]({destination})"
        return f"[{reference.display_name}]({destination})"

    def _render_link(self, node: _Node) -> str:
        href = node.attrs.get("href", "")
        label = self._render_children(node, inline=True).strip()
        if not label:
            label = href
        if not href:
            return label
        resolved = self.link_resolver(href, label)
        return f"[{label}]({self._link_destination(resolved)})"

    @staticmethod
    def _link_destination(value: str) -> str:
        # Keep ordinary URL punctuation readable while escaping spaces and
        # parentheses that would otherwise terminate a Markdown destination.
        return quote(value, safe=":/?#[]@!$&'*,;=%-._~")

    def _render_pre(self, node: _Node) -> str:
        raw = self._raw_text(node)
        if not raw.strip():
            return ""
        fence = "````" if "```" in raw else "```"
        return f"\n\n{fence}\n{raw.strip(chr(10))}\n{fence}\n\n"

    def _raw_text(self, node: _Node) -> str:
        if node.tag is None:
            return node.data
        return "".join(self._raw_text(child) for child in node.children)

    def _render_list(self, node: _Node, *, depth: int) -> str:
        ordered = node.tag == "ol"
        try:
            number = int(node.attrs.get("start", "1"))
        except ValueError:
            number = 1
        indent = "  " * depth
        lines: list[str] = []
        for child in node.children:
            if child.tag != "li":
                continue
            body_parts: list[str] = []
            nested: list[_Node] = []
            for item in child.children:
                if item.tag in {"ul", "ol"}:
                    nested.append(item)
                else:
                    body_parts.append(self._render(item))
            body = "".join(body_parts).strip()
            body_lines = body.splitlines() or [""]
            marker = f"{number}. " if ordered else "- "
            lines.append(f"{indent}{marker}{body_lines[0].strip()}")
            lines.extend(f"{indent}  {line.rstrip()}" for line in body_lines[1:] if line.strip())
            for nested_list in nested:
                nested_text = self._render_list(nested_list, depth=depth + 1).strip()
                if nested_text:
                    lines.extend(nested_text.splitlines())
            number += 1
        rendered_lines = "\n".join(lines)
        return f"\n\n{rendered_lines}\n\n" if lines else ""

    def _render_table(self, node: _Node) -> str:
        rows: list[list[str]] = []

        def collect(current: _Node) -> None:
            if current.tag == "tr":
                cells: list[str] = []
                for cell in current.children:
                    if cell.tag in {"td", "th"}:
                        value = self._render_children(cell, inline=True).strip()
                        value = re.sub(r"\s+", " ", value).replace("|", r"\|")
                        cells.append(value)
                if cells:
                    rows.append(cells)
                return
            for child in current.children:
                if child.tag is not None:
                    collect(child)

        collect(node)
        if not rows:
            return ""
        width = max(len(row) for row in rows)
        padded = [row + [""] * (width - len(row)) for row in rows]
        header = padded[0]
        separator = ["---"] * width
        lines = [
            f"| {' | '.join(header)} |",
            f"| {' | '.join(separator)} |",
        ]
        lines.extend(f"| {' | '.join(row)} |" for row in padded[1:])
        rendered_lines = "\n".join(lines)
        return f"\n\n{rendered_lines}\n\n"

    @staticmethod
    def _clean_document(value: str) -> str:
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        output: list[str] = []
        in_fence = False
        for line in value.split("\n"):
            if re.match(r"^\s*`{3,}", line):
                in_fence = not in_fence
                output.append(line.rstrip())
                continue
            if in_fence:
                output.append(line.rstrip("\r"))
                continue
            line = re.sub(r"[ \t]+$", "", line)
            if not line.strip():
                if output and output[-1] != "":
                    output.append("")
            else:
                output.append(line)
        cleaned = "\n".join(output).strip()
        return f"{cleaned}\n" if cleaned else ""


__all__ = ["AssetReference", "MarkdownRenderer", "_normalise_title"]
