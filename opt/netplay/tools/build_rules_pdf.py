from __future__ import annotations

from pathlib import Path


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def build_pdf_bytes(lines: list[str]) -> bytes:
    content_lines = ["BT", "/F1 12 Tf", "72 744 Td", "14 TL"]
    for line in lines:
        if line.strip():
            content_lines.append(f"({_escape(line)}) Tj")
        content_lines.append("T*")
    content_lines.append("ET")
    stream = "\n".join(content_lines) + "\n"
    stream_bytes = stream.encode("utf-8")

    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream_bytes)} >>\nstream\n{stream}endstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n")
    offsets = [0]
    for idx, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode("utf-8"))
        pdf.extend(body.encode("utf-8"))
        pdf.extend(b"\nendobj\n")

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)+1}\n".encode("utf-8"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("utf-8"))
    pdf.extend(b"trailer\n")
    pdf.extend(f"<< /Size {len(objects)+1} /Root 1 0 R >>\n".encode("utf-8"))
    pdf.extend(f"startxref\n{xref_pos}\n%%EOF\n".encode("utf-8"))
    return bytes(pdf)


def main() -> None:
    docs_dir = Path("docs")
    rules_txt = docs_dir / "rules_a.txt"
    lines = rules_txt.read_text(encoding="utf-8").splitlines()
    pdf_bytes = build_pdf_bytes(lines)
    out_path = docs_dir / "rules_a.pdf"
    out_path.write_bytes(pdf_bytes)


if __name__ == "__main__":
    main()
