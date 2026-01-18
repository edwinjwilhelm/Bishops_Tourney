#!/usr/bin/env python3
"""
Zero-dependency Markdown-to-PDF helper.

This does NOT fully render Markdown. It treats the input as plain text,
wraps lines crudely, and writes them into a minimal PDF using Type1 Helvetica.
Goal: Always produce a rules.pdf on a clean machine (no reportlab/markdown).

Usage:
  python tools/md_to_pdf.py <input.md> <output.pdf>
"""
import sys
import os
from typing import List

# Letter sized page in points (1 pt = 1/72")
PAGE_W, PAGE_H = 612, 792
MARGIN = 36             # 0.5 inch
FONT_SIZE = 10
LEADING = 14
MAX_TEXT_W = PAGE_W - 2 * MARGIN

# Approximate per-character width (Helvetica 10pt). Not accurate but OK for wrapping.
AVG_CHAR_W = 5.0


def wrap_lines(text: str, max_width_pts: float) -> List[str]:
    lines: List[str] = []
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    for raw in text.split('\n'):
        if raw.strip() == "":
            lines.append("")
            continue
        cur = ""
        for word in raw.split(' '):
            test = (cur + " " + word).strip()
            if len(test) * AVG_CHAR_W <= max_width_pts:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                # Hard split a single overlong word
                w = word
                while len(w) * AVG_CHAR_W > max_width_pts and len(w) > 0:
                    take = max(1, int(max_width_pts // AVG_CHAR_W))
                    lines.append(w[:take])
                    w = w[take:]
                cur = w
        lines.append(cur)
    return lines


def escape_pdf_text(s: str) -> str:
    # Restrict to ASCII for simplicity and escape special chars
    s = s.encode('ascii', errors='replace').decode('ascii')
    s = s.replace('\\', r'\\').replace('(', r'\(').replace(')', r'\)')
    return s


def build_pdf(pages_streams: List[bytes]) -> bytes:
    objs: List[bytes] = []

    def add(body: str):
        objs.append(body.encode('latin1'))

    # 1: Catalog
    add("<< /Type /Catalog /Pages 2 0 R >>\n")
    # 2: Pages (kids filled after computing page object numbers)
    kids = []
    for i in range(len(pages_streams)):
        kids.append(f"{3 + 2*i} 0 R")
    add(f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>\n")

    # Per page: Page, then Contents
    font_obj_num = 3 + 2*len(pages_streams)
    for i, stream in enumerate(pages_streams):
        # Page
        add(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] "
            "/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>\n" % (
                PAGE_W, PAGE_H, font_obj_num, 4 + 2*i
            )
        )
        # Contents
        add("<< /Length %d >>\nstream\n%s\nendstream\n" % (len(stream), stream.decode('latin1', errors='ignore')))

    # Font
    add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n")

    # Assemble PDF
    out = bytearray()
    out += b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0]
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode('latin1')
        out += body
        out += b"endobj\n"

    xref_pos = len(out)
    out += f"xref\n0 {len(objs)+1}\n".encode('latin1')
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode('latin1')
    out += b"trailer\n"
    out += f"<< /Size {len(objs)+1} /Root 1 0 R >>\n".encode('latin1')
    out += b"startxref\n"
    out += f"{xref_pos}\n".encode('latin1')
    out += b"%%EOF\n"
    return bytes(out)


def make_page_streams(lines: List[str]) -> List[bytes]:
    y_start = PAGE_H - MARGIN
    y = y_start
    pages: List[bytes] = []
    chunks: List[str] = ["BT", f"/F1 {FONT_SIZE} Tf", f"{LEADING} TL", f"{MARGIN} {y_start - LEADING} Td"]
    first = True
    for line in lines:
        if y - LEADING < MARGIN:
            chunks.append("ET")
            pages.append("\n".join(chunks).encode('latin1'))
            chunks = ["BT", f"/F1 {FONT_SIZE} Tf", f"{LEADING} TL", f"{MARGIN} {y_start - LEADING} Td"]
            y = y_start
            first = True
        safe = escape_pdf_text(line)
        if first:
            chunks.append(f"({safe}) Tj")
            first = False
        else:
            chunks.append("T*")
            chunks.append(f"({safe}) Tj")
        y -= LEADING
    chunks.append("ET")
    pages.append("\n".join(chunks).encode('latin1'))
    return pages


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print('Usage: md_to_pdf.py <input.md> <output.pdf>')
        return 2
    in_md, out_pdf = argv
    try:
        with open(in_md, 'r', encoding='utf-8') as f:
            text = f.read()
        lines = wrap_lines(text, MAX_TEXT_W)
        pages = make_page_streams(lines)
        pdf_bytes = build_pdf(pages)
        os.makedirs(os.path.dirname(os.path.abspath(out_pdf)), exist_ok=True)
        with open(out_pdf, 'wb') as f:
            f.write(pdf_bytes)
        if os.path.getsize(out_pdf) <= 0:
            print('[md_to_pdf] output is empty')
            return 2
        return 0
    except Exception as e:
        print(f'[md_to_pdf] error: {e}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
