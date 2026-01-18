#!/usr/bin/env python3
"""
Export RULES_REFERENCE from Bishops_Golden.py to docs/rules.txt and docs/rules.pdf (when possible).

Usage:
  python tools/export_rules.py               # writes TXT, tries PDF
  python tools/export_rules.py --txt         # write TXT only
  python tools/export_rules.py --pdf         # write PDF only (falls back to TXT if PDF not possible)
  python tools/export_rules.py --out docs    # custom output directory
  python tools/export_rules.py --quiet       # suppress info messages

Exit codes:
  0 = success, 1 = partial (txt only when pdf requested), 2 = failure
"""
from __future__ import annotations
import os
import sys
import argparse
import importlib.util
from typing import Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN_PATH = os.path.join(ROOT, 'Bishops_Golden.py')


def _load_engine(path: str):
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    spec = importlib.util.spec_from_file_location('bg_engine_rules', path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def _ensure_out_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_txt(rules: str, out_dir: str, quiet: bool) -> str:
    _ensure_out_dir(out_dir)
    txt_path = os.path.join(out_dir, 'rules.txt')
    REQUIRED_TAIL = "To prevent unauthorized reproduction a minor false rule has been included in this limited edition."
    text = rules.strip()
    # Ensure REQUIRED_TAIL is present exactly once and at the end
    if REQUIRED_TAIL not in text:
        text = text + "\n" + REQUIRED_TAIL
    else:
        # Move to end if not already the last non-empty line
        lines = [ln.rstrip() for ln in text.splitlines() if ln.strip() != ""]
        if lines and lines[-1] != REQUIRED_TAIL:
            text = "\n".join([ln for ln in text.splitlines() if ln.strip() != REQUIRED_TAIL])
            text = text.rstrip() + "\n" + REQUIRED_TAIL
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(text.strip() + '\n')
    if not quiet:
        print(f"[rules] wrote {txt_path} ({len(rules.strip())} chars)")
    return txt_path


def _try_pdf(rules: str, out_dir: str, quiet: bool) -> Tuple[bool, str]:
    _ensure_out_dir(out_dir)
    pdf_path = os.path.join(out_dir, 'rules.pdf')
    REQUIRED_TAIL = "To prevent unauthorized reproduction a minor false rule has been included in this limited edition."
    # Prefer reportlab if installed, otherwise use md_to_pdf in-process, then subprocess as last resort
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
    except Exception:
        # First try importing tools/md_to_pdf for an in-process generation (no subprocess)
        try:
            sys.path.append(os.path.join(ROOT, 'tools'))
            import md_to_pdf as mdpdf  # type: ignore
            # Ensure REQUIRED_TAIL at the end (match TXT behavior)
            text = rules.replace('\r\n', '\n').replace('\r', '\n').strip()
            REQUIRED_TAIL = "To prevent unauthorized reproduction a minor false rule has been included in this limited edition."
            if REQUIRED_TAIL not in text:
                text = text + "\n" + REQUIRED_TAIL
            else:
                lines = [ln.rstrip() for ln in text.splitlines() if ln.strip() != ""]
                if lines and lines[-1] != REQUIRED_TAIL:
                    text = "\n".join([ln for ln in text.splitlines() if ln.strip() != REQUIRED_TAIL])
                    text = text.rstrip() + "\n" + REQUIRED_TAIL
            # Build PDF bytes
            wrapped = mdpdf.wrap_lines(text + '\n', getattr(mdpdf, 'MAX_TEXT_W', 540))
            pages = mdpdf.make_page_streams(wrapped)
            pdf_bytes = mdpdf.build_pdf(pages)
            with open(pdf_path, 'wb') as f:
                f.write(pdf_bytes)
            if os.path.getsize(pdf_path) > 0:
                if not quiet:
                    print(f"[rules] wrote {pdf_path} (md_to_pdf inline)")
                return True, pdf_path
        except Exception as e_inline:
            if not quiet:
                print(f"[rules] md_to_pdf inline failed: {e_inline} — trying subprocess fallback")
        # Fallback: use tools/md_to_pdf.py via subprocess
        md_script = os.path.join(ROOT, 'tools', 'md_to_pdf.py')
        if os.path.exists(md_script):
            md_tmp = os.path.join(out_dir, '_rules_tmp.md')
            try:
                with open(md_tmp, 'w', encoding='utf-8') as f:
                    f.write(rules.strip() + '\n')
                import subprocess
                res = subprocess.run([sys.executable or 'python', md_script, md_tmp, pdf_path], capture_output=True, text=True)
                ok = (res.returncode == 0 and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0)
                if ok:
                    try:
                        os.remove(md_tmp)
                    except Exception:
                        pass
                    if not quiet:
                        print(f"[rules] wrote {pdf_path} via md_to_pdf.py (subprocess)")
                    return True, pdf_path
                else:
                    if not quiet:
                        print(f"[rules] md_to_pdf subprocess failed (rc={res.returncode}) — TXT only")
            except Exception as e:
                if not quiet:
                    print(f"[rules] md_to_pdf subprocess exception: {e} — TXT only")
        # As a last resort, signal failure (TXT will already be present)
        return False, ''

    # Simple plain-text PDF layout with reportlab
    text = rules.replace('\r\n', '\n').replace('\r', '\n').strip()
    # Ensure REQUIRED_TAIL at end
    if REQUIRED_TAIL not in text:
        text = text + "\n" + REQUIRED_TAIL
    else:
        lines = [ln.rstrip() for ln in text.splitlines() if ln.strip() != ""]
        if lines and lines[-1] != REQUIRED_TAIL:
            text = "\n".join([ln for ln in text.splitlines() if ln.strip() != REQUIRED_TAIL])
            text = text.rstrip() + "\n" + REQUIRED_TAIL
    text = text + '\n'
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4
    margin = 0.5 * inch
    max_width = width - 2 * margin
    x = margin
    y = height - margin
    line_height = 12
    c.setTitle('Bishops Rules')
    c.setAuthor('Bishops Golden Engine')
    for paragraph in text.split('\n\n'):
        for line in paragraph.split('\n'):
            words = line.split(' ')
            cur_line = ''
            for w in words:
                test = (cur_line + ' ' + w).strip()
                if c.stringWidth(test, 'Helvetica', 10) < max_width:
                    cur_line = test
                else:
                    y -= line_height
                    if y < margin:
                        c.showPage(); y = height - margin
                    c.setFont('Helvetica', 10)
                    c.drawString(x, y, cur_line)
                    cur_line = w
            if cur_line:
                y -= line_height
                if y < margin:
                    c.showPage(); y = height - margin
                c.setFont('Helvetica', 10)
                c.drawString(x, y, cur_line)
        y -= line_height * 0.5
    c.save()
    if not quiet:
        print(f"[rules] wrote {pdf_path} (reportlab)")
    return True, pdf_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'docs'))
    ap.add_argument('--txt', action='store_true', help='write txt only')
    ap.add_argument('--pdf', action='store_true', help='write pdf only (txt fallback if pdf unavailable)')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args(argv)

    try:
        mod = _load_engine(GOLDEN_PATH)
        rules = getattr(mod, 'RULES_REFERENCE', '')
        if not isinstance(rules, str) or not rules.strip():
            print('[rules] RULES_REFERENCE not found or empty in Golden engine')
            return 2
        wrote_any = False
        partial = False
        if args.pdf and not args.txt:
            ok, _ = _try_pdf(rules, args.out, args.quiet)
            if not ok:
                _write_txt(rules, args.out, args.quiet)
                partial = True
            wrote_any = True
        elif args.txt and not args.pdf:
            _write_txt(rules, args.out, args.quiet)
            wrote_any = True
        else:
            # default: write txt and try pdf
            _write_txt(rules, args.out, args.quiet)
            ok, _ = _try_pdf(rules, args.out, args.quiet)
            wrote_any = True
            partial = not ok
        if wrote_any and not partial:
            return 0
        if wrote_any and partial:
            return 1
        return 2
    except Exception as e:
        if not args.quiet:
            print(f"[rules] exception: {e}")
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
