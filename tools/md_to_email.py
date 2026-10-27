#!/usr/bin/env python3
"""Render scripts/*.md into email-friendly HTML + plain text under downloads/.

The HTML is written with inline-ish styles and a Bengali-first font stack so it can
be pasted straight into an email body, printed to PDF, or opened in a browser.
"""
from __future__ import annotations

import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "media"

TEMPLATE = """<!doctype html>
<html lang="bn">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body{{
    margin:0; padding:36px 18px 80px;
    background:#f4f6f8; color:#16191d;
    font:17px/1.95 "Noto Sans Bengali","Hind Siliguri","SolaimanLipi","Kalpurush",
         ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  }}
  .page{{max-width:820px; margin:0 auto; background:#fff; padding:44px 46px 60px;
        border:1px solid #e2e6ea; border-radius:14px;
        box-shadow:0 12px 40px rgba(16,24,40,.08)}}
  h1{{font-size:30px; line-height:1.45; margin:0 0 18px; letter-spacing:-.01em;
      border-bottom:3px solid #0f62fe; padding-bottom:14px}}
  h2{{font-size:22px; line-height:1.5; margin:38px 0 12px; color:#0b1f4b}}
  h3{{font-size:19px; margin:26px 0 10px}}
  p{{margin:0 0 14px}}
  blockquote{{
    margin:14px 0 18px; padding:12px 20px;
    background:#f2f7ff; border-left:4px solid #0f62fe; border-radius:0 8px 8px 0;
    color:#12233f;
  }}
  blockquote p{{margin:0 0 10px}}
  blockquote p:last-child{{margin:0}}
  code{{background:#f1f3f5; padding:2px 6px; border-radius:5px;
        font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace; font-size:14px}}
  pre{{background:#0d1117; color:#e6edf3; padding:16px 18px; border-radius:10px;
       overflow-x:auto; font-size:13.5px; line-height:1.7}}
  pre code{{background:none; color:inherit; padding:0}}
  table{{border-collapse:collapse; width:100%; margin:16px 0 22px; font-size:15.5px}}
  th,td{{border:1px solid #dfe3e8; padding:9px 11px; text-align:left; vertical-align:top}}
  th{{background:#eef2f7; font-weight:700}}
  tr:nth-child(even) td{{background:#fafbfc}}
  hr{{border:0; border-top:1px solid #e2e6ea; margin:32px 0}}
  ol,ul{{margin:0 0 16px; padding-left:26px}}
  li{{margin-bottom:6px}}
  strong{{color:#0b1f4b}}
  @media print{{
    body{{background:#fff; padding:0}}
    .page{{border:0; box-shadow:none; padding:0; max-width:none}}
    pre{{background:#f5f5f5; color:#111}}
  }}
</style>
</head>
<body>
<div class="page">
{body}
</div>
</body>
</html>
"""


def md_to_text(md: str) -> str:
    """Crude but readable plain-text fallback for email bodies / Notepad."""
    txt = md
    txt = re.sub(r"^#{1,6}\s*", "", txt, flags=re.M)          # headings
    txt = re.sub(r"\*\*(.+?)\*\*", r"\1", txt)                 # bold
    txt = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"\1", txt)   # italic
    txt = re.sub(r"`([^`]+?)`", r"\1", txt)                    # inline code
    txt = re.sub(r"^>\s?", "", txt, flags=re.M)                # quotes
    txt = re.sub(r"^---+$", "-" * 60, txt, flags=re.M)         # rules
    txt = re.sub(r"\|", "  ", txt)                             # table pipes
    return txt.strip() + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    built = []
    for src in sorted((ROOT / "scripts").glob("*.md")):
        raw = src.read_text(encoding="utf-8")
        title = src.stem.replace("_", " ").title()
        body = markdown.markdown(
            raw, extensions=["tables", "fenced_code", "sane_lists", "nl2br"]
        )
        html_name = src.stem + ".html"
        txt_name = src.stem + ".txt"
        (OUT / html_name).write_text(
            TEMPLATE.format(title=title, body=body), encoding="utf-8"
        )
        (OUT / txt_name).write_text(md_to_text(raw), encoding="utf-8")
        (OUT / src.name).write_text(raw, encoding="utf-8")  # keep the .md too
        built += [src.name, html_name, txt_name]
        print(f"[ok] {src.name} -> {html_name}, {txt_name}")
    print("\nfiles in media/:")
    for name in sorted(built):
        size = (OUT / name).stat().st_size
        print(f"  {name:38s} {size/1024:7.1f} KB")


if __name__ == "__main__":
    main()
