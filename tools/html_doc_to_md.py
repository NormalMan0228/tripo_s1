"""Writes a GitHub-readable README.md next to each report page (index.html).

GitHub shows .html files as source code, so teammates could not read the character pipeline
reports there. This keeps the HTML as the original and adds a Markdown copy beside it:
headings, paragraphs, lists, tables, images and captions. Inline SVG diagrams are saved as
fig_<n>.svg with the page's light colours filled in, so GitHub draws them as images.

    python tools/html_doc_to_md.py docs/character_pipeline/*/index.html
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# Light-theme values of the CSS variables the report pages use inside their SVG diagrams.
SVG_STYLE = """<style>
text{font-family:"Malgun Gothic","Apple SD Gothic Neo",sans-serif}
.s-ink{fill:#1B1F27}.s-muted{fill:#5B6473}.s-paper{fill:#fff}.s-soft{fill:#EEF1F6}.s-acc{fill:#2F5BD3}.s-good{fill:#1E8A52}.s-bad{fill:#C83A32}.s-warn{fill:#B26A00}
.st-acc{stroke:#2F5BD3}.st-good{stroke:#1E8A52}.st-ink{stroke:#1B1F27}.st-muted{stroke:#5B6473}.st-bad{stroke:#C83A32}.st-warn{stroke:#B26A00}
</style>"""
VARS = {"--ink": "#1B1F27", "--muted": "#5B6473", "--paper": "#fff", "--soft": "#EEF1F6", "--line": "#DDE1E8",
        "--accent": "#2F5BD3", "--good": "#1E8A52", "--bad": "#C83A32", "--warn": "#B26A00", "--bg": "#F5F6F8"}
SKIP = {"head", "style", "script", "title", "nav", "button"}
VOID_SKIP = {"link", "meta"}
BLOCK = {"p", "div", "section", "main", "article", "header", "footer"}


def inline(text: str) -> str:
    return re.sub(r"[ \t\r\n]+", " ", text)


class Converter(HTMLParser):
    def __init__(self, folder: Path):
        super().__init__(convert_charrefs=True)
        self.folder, self.out, self.buf = folder, [], []
        self.skip = 0
        self.lists: list[list] = []          # [kind, counter]
        self.table: list[list[str]] | None = None
        self.cell: list[str] | None = None
        self.quote = 0
        self.svg: list[str] | None = None
        self.svg_depth, self.figures = 0, 0
        self.caption = False
        self.href: list[str] = []
        self.blocks: list[bool] = []         # open block tags: True when it is a quote box

    # --- output helpers -------------------------------------------------------------------------
    def target(self) -> list[str]:
        return self.cell if self.cell is not None else self.buf

    def write(self, text: str) -> None:
        self.target().append(text)

    def flush(self, prefix: str = "") -> None:
        text = inline("".join(self.buf)).strip()
        self.buf = []
        if not text: return
        if self.quote: prefix = "> " + prefix
        self.out.append(prefix + text)
        self.out.append("")

    # --- svg passthrough --------------------------------------------------------------------------
    def svg_tag(self, tag, attrs, close=False, empty=False):
        if close:
            self.svg.append(f"</{tag}>"); return
        parts = "".join(f' {k}="{(v or "").replace(chr(34), "&quot;")}"' for k, v in attrs)
        self.svg.append(f"<{tag}{parts}{'/' if empty else ''}>")

    def save_svg(self) -> None:
        self.figures += 1
        body = "".join(self.svg)
        for name, value in VARS.items(): body = body.replace(f"var({name})", value)
        if "xmlns=" not in body[:200]: body = body.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
        first = body.index(">") + 1
        body = body[:first] + SVG_STYLE + body[first:]
        name = f"fig_{self.figures}.svg"
        (self.folder / name).write_text(body, encoding="utf-8")
        self.flush()
        self.out += [f"![그림 {self.figures}]({name})", ""]
        self.svg = None

    # --- parser events ----------------------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        if self.svg is not None:
            self.svg_depth += tag == "svg"; self.svg_tag(tag, attrs); return
        if tag in VOID_SKIP: return
        if self.skip or tag in SKIP:
            self.skip += tag in SKIP; return
        a = dict(attrs)
        if tag == "svg":
            self.svg, self.svg_depth = [], 1; self.svg_tag(tag, attrs); return
        if tag in ("h1", "h2", "h3", "h4"): self.flush()
        elif tag in BLOCK:
            self.flush()
            box = "box" in (a.get("class") or "").split()
            self.blocks.append(box)
            self.quote += box
        elif tag in ("ul", "ol"):
            self.flush(); self.lists.append([tag, 0])
        elif tag == "li":
            self.flush(self.item_prefix())
            if self.lists: self.lists[-1][1] += 1
        elif tag == "br": self.write(" <br> " if self.cell is not None else "\n")
        elif tag in ("b", "strong"): self.write("**")
        elif tag in ("i", "em"): self.write("*")
        elif tag == "code": self.write("`")
        elif tag == "a": self.href.append(a.get("href") or ""); self.write("[")
        elif tag == "img":
            self.flush()
            self.out += [f"![{a.get('alt', '')}]({a.get('src', '')})", ""]
        elif tag == "figcaption": self.flush(); self.caption = True
        elif tag == "table": self.flush(); self.table = []
        elif tag == "tr" and self.table is not None: self.table.append([])
        elif tag in ("td", "th") and self.table is not None: self.cell = []

    def handle_startendtag(self, tag, attrs):
        if self.svg is not None: self.svg_tag(tag, attrs, empty=True); return
        self.handle_starttag(tag, attrs)

    def item_prefix(self) -> str:
        if not self.lists: return ""
        kind, count = self.lists[-1]
        indent = "  " * (len(self.lists) - 1)
        return indent + (f"{count + 1}. " if kind == "ol" else "- ")

    def handle_endtag(self, tag):
        if self.svg is not None:
            self.svg_tag(tag, None, close=True)
            if tag == "svg":
                self.svg_depth -= 1
                if self.svg_depth == 0: self.save_svg()
            return
        if self.skip:
            self.skip -= tag in SKIP; return
        if tag in ("h1", "h2", "h3", "h4"): self.flush("#" * int(tag[1]) + " ")
        elif tag in BLOCK:
            self.flush()
            if self.blocks and self.blocks.pop(): self.quote -= 1
        elif tag in ("ul", "ol"):
            self.flush(self.item_prefix())
            if self.lists: self.lists.pop()
        elif tag == "li": self.flush(self.item_prefix_done())
        elif tag in ("b", "strong"): self.write("**")
        elif tag in ("i", "em"): self.write("*")
        elif tag == "code": self.write("`")
        elif tag == "a": self.write(f"]({self.href.pop() if self.href else ''})")
        elif tag == "figcaption":
            text = inline("".join(self.buf)).strip(); self.buf = []
            if text: self.out += [f"*{text}*", ""]
            self.caption = False
        elif tag in ("td", "th") and self.cell is not None:
            self.table[-1].append(inline("".join(self.cell)).strip().replace("|", "\\|"))
            self.cell = None
        elif tag == "table" and self.table is not None:
            rows = [r for r in self.table if r]
            self.table = None
            if not rows: return
            width = max(len(r) for r in rows)
            rows = [r + [""] * (width - len(r)) for r in rows]
            self.out.append("| " + " | ".join(rows[0]) + " |")
            self.out.append("|" + "---|" * width)
            self.out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
            self.out.append("")

    def item_prefix_done(self) -> str:
        # The li counter was already advanced at the start tag.
        if not self.lists: return ""
        kind, count = self.lists[-1]
        indent = "  " * (len(self.lists) - 1)
        return indent + (f"{count}. " if kind == "ol" else "- ")

    def handle_data(self, data):
        if self.svg is not None:
            self.svg.append(data.replace("&", "&amp;").replace("<", "&lt;")); return
        if self.skip: return
        self.write(data)


def convert(page: Path) -> Path:
    html = page.read_text(encoding="utf-8")
    parser = Converter(page.parent)
    parser.feed(html)
    parser.flush()
    lines, blank = [], False
    for line in parser.out:
        if not line.strip():
            if not blank: lines.append("")
            blank = True
        else:
            lines.append(line.rstrip()); blank = False
    note = f"> GitHub에서 읽기 쉽게 [{page.name}]({page.name})을 옮긴 사본입니다. 원본(HTML)을 내려받아 브라우저로 열면 원래 모양으로 보입니다.\n\n"
    target = page.with_name("README.md")
    target.write_text(note + "\n".join(lines).strip() + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        out = convert(Path(arg))
        print(out, len(out.read_text(encoding="utf-8")), "chars,", len(list(out.parent.glob("fig_*.svg"))), "svg")
