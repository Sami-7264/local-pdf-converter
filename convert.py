#!/usr/bin/env python3
"""
Local PDF converter: PDF -> DOCX / TXT / PNG / JPG, and images -> PDF.

Usage:
    python convert.py input.pdf [output.docx] [--to docx|txt|png|jpg] [--pages 1-3,5] [--dpi 150]
    python convert.py photo.jpg [output.pdf]
    python convert.py --folder ./pdfs [--to FORMAT] [--overwrite]
    python convert.py --folder ./scans --to pdf --combine
    python convert.py --gui
"""

import argparse
import logging
import sys
import warnings
from pathlib import Path

# pdf2docx still imports PyMuPDF under its old name "fitz", which prints a
# deprecation warning on newer versions. It is harmless, so hide it.
warnings.filterwarnings("ignore", category=FutureWarning, message=".*fitz.*")

import pymupdf  # installed automatically with pdf2docx
from pdf2docx import Converter

# pdf2docx logs every parsing step at INFO level; keep only warnings and errors.
logging.getLogger().setLevel(logging.WARNING)

PDF_TARGETS = ("docx", "txt", "png", "jpg")  # what a PDF can become
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff"}  # what can become a PDF


class ConversionError(Exception):
    """Raised for problems we can explain to the user in plain words."""


# ---------------------------------------------------------------- helpers

def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def resolve_target(src: Path, target: str | None, output: str | None) -> str:
    """Pick the output format: --to, else the output file's extension, else a sensible default."""
    if target:
        fmt = target.lower().lstrip(".")
    elif output:
        fmt = Path(output).suffix.lower().lstrip(".")
    else:
        fmt = "pdf" if is_image(src) else "docx"
    fmt = "jpg" if fmt == "jpeg" else fmt

    allowed = ("pdf",) if is_image(src) else PDF_TARGETS
    if fmt not in allowed:
        kind = "an image" if is_image(src) else "a PDF"
        raise ConversionError(f"Can't convert {kind} to '{fmt}'. Supported: {', '.join(allowed)}")
    return fmt


def open_pdf(pdf_path: Path) -> pymupdf.Document:
    """Open a PDF, making sure it is real, unlocked and not empty. Caller must close it."""
    try:
        doc = pymupdf.open(pdf_path)
    except Exception:
        raise ConversionError(f"Not a valid PDF file: {pdf_path}")

    problem = None
    if not doc.is_pdf:
        problem = f"Not a valid PDF file: {pdf_path}"
    elif doc.needs_pass:
        problem = f"PDF is password protected: {pdf_path}"
    elif doc.page_count == 0:
        problem = f"PDF has no pages: {pdf_path}"
    if problem:
        doc.close()
        raise ConversionError(problem)
    return doc


def parse_pages(spec: str | None, page_count: int) -> list[int]:
    """Turn '1-3,5' into zero-based page indexes [0, 1, 2, 4]. None means all pages."""
    if not spec:
        return list(range(page_count))

    pages = set()
    for part in spec.split(","):
        part = part.strip()
        try:
            if "-" in part:
                first, last = part.split("-", 1)
                first, last = int(first or 1), int(last or page_count)  # "3-" means 3 to the end
            else:
                first = last = int(part)
        except ValueError:
            raise ConversionError(f"Invalid page range '{spec}' (example: 1-3,5)")
        if not 1 <= first <= last <= page_count:
            raise ConversionError(f"Pages '{part}' are out of range: the PDF has {page_count} page(s)")
        pages.update(range(first - 1, last))
    return sorted(pages)


def confirm_overwrite(existing: list[Path]) -> bool:
    """Ask in the terminal whether existing files may be replaced."""
    if not sys.stdin.isatty():
        # No one to ask (e.g. running from a script): play it safe.
        return False
    what = f"'{existing[0].name}' already exists" if len(existing) == 1 else f"{len(existing)} output files already exist"
    try:
        answer = input(f"{what}. Overwrite? [y/N] ").strip().lower()
    except EOFError:  # Ctrl-D counts as "no"
        print()
        return False
    return answer in ("y", "yes")


# ------------------------------------------------------------ converters

def pdf_to_docx(pdf_path: Path, out: Path, pages: list[int]) -> None:
    cv = Converter(str(pdf_path))
    try:
        cv.convert(str(out), pages=pages)
    finally:
        cv.close()


def pdf_to_txt(doc: pymupdf.Document, out: Path, pages: list[int]) -> None:
    text = "\n\n".join(doc[i].get_text().strip() for i in pages)
    out.write_text(text + "\n", encoding="utf-8")


def pdf_to_images(doc: pymupdf.Document, outs: list[Path], pages: list[int], dpi: int) -> None:
    for i, out in zip(pages, outs):
        doc[i].get_pixmap(dpi=dpi).save(out)


def images_to_pdf(images: list[Path], out: Path) -> None:
    """Put each image on its own page, in the given order."""
    result = pymupdf.open()
    try:
        for img in images:
            try:
                with pymupdf.open(img) as picture:
                    pdf_bytes = picture.convert_to_pdf()
            except Exception:
                raise ConversionError(f"Not a valid image file: {img}")
            with pymupdf.open("pdf", pdf_bytes) as page:
                result.insert_pdf(page)
        result.save(out)
    finally:
        result.close()


# ------------------------------------------------------------- main flow

def convert_file(src, output=None, target=None, pages=None, dpi=150,
                 overwrite=False, ask=confirm_overwrite) -> bool:
    """Convert one file. Returns True on success, False if skipped or failed.

    `ask` is called with the list of output files that already exist; the GUI
    passes its own dialog here instead of the terminal prompt.
    """
    src = Path(src)
    try:
        fmt = resolve_target(src, target, output)
        print(f"Converting: {src} -> {fmt.upper()}")
        if not src.is_file():
            raise ConversionError(f"File not found: {src}")

        if fmt == "pdf":  # image -> PDF
            outs = [Path(output) if output else src.with_suffix(".pdf")]
            if not may_write(outs, overwrite, ask):
                return False
            images_to_pdf([src], outs[0])

        else:  # PDF -> something
            doc = open_pdf(src)
            try:
                page_list = parse_pages(pages, doc.page_count)
                if fmt in ("png", "jpg"):
                    # One image per page: report.pdf -> report_p1.png, report_p2.png, ...
                    base = Path(output) if output else src
                    outs = [base.with_name(f"{base.stem}_p{i + 1}.{fmt}") for i in page_list]
                else:
                    outs = [Path(output) if output else src.with_suffix(f".{fmt}")]
                if not may_write(outs, overwrite, ask):
                    return False

                if fmt in ("docx", "txt") and not any(doc[i].get_text().strip() for i in page_list):
                    print("  Note: no text found. This looks like a scanned PDF; the result will not be editable text.")

                if fmt == "docx":
                    pdf_to_docx(src, outs[0], page_list)
                elif fmt == "txt":
                    pdf_to_txt(doc, outs[0], page_list)
                else:
                    pdf_to_images(doc, outs, page_list, dpi)
            finally:
                doc.close()

    except ConversionError as e:
        print(f"  Error: {e}")
        return False
    except Exception as e:  # anything unexpected from the libraries
        print(f"  Error: conversion failed for {src.name}: {e or type(e).__name__}")
        return False

    if len(outs) == 1:
        print(f"  Success: saved {outs[0]}")
    else:
        print(f"  Success: saved {len(outs)} files ({outs[0].name} ... {outs[-1].name})")
    return True


def may_write(outs: list[Path], overwrite: bool, ask) -> bool:
    """True if we may write all output files (none exist, --overwrite, or the user agreed)."""
    existing = [p for p in outs if p.exists()]
    if not existing or overwrite or ask(existing):
        return True
    print(f"  Skipped: {existing[0]} already exists (use --overwrite to replace it).")
    return False


def convert_folder(folder: Path, target=None, pages=None, dpi=150, overwrite=False, combine=False) -> bool:
    """Convert every matching file in a folder (not subfolders), saving results alongside.

    With --to pdf the folder's images are converted; otherwise its PDFs are.
    With --combine, all images go into one PDF named after the folder.
    """
    folder = Path(folder)
    if not folder.is_dir():
        print(f"Error: folder not found: {folder}")
        return False

    want_images = (target or "").lower() == "pdf"
    files = sorted(p for p in folder.iterdir()
                   if p.is_file() and (is_image(p) if want_images else p.suffix.lower() == ".pdf"))
    if not files:
        print(f"No {'image' if want_images else 'PDF'} files found in {folder}")
        return False

    if combine:
        if not want_images:
            print("Error: --combine only works with --to pdf (images -> one PDF)")
            return False
        out = folder / f"{folder.resolve().name}.pdf"
        print(f"Combining {len(files)} image(s) into {out}")
        if not may_write([out], overwrite, confirm_overwrite):
            return False
        try:
            images_to_pdf(files, out)
        except ConversionError as e:
            print(f"  Error: {e}")
            return False
        print(f"  Success: saved {out}")
        return True

    print(f"Found {len(files)} file(s) in {folder}\n")
    ok = sum(convert_file(f, target=target, pages=pages, dpi=dpi, overwrite=overwrite) for f in files)
    print(f"\nDone: {ok} of {len(files)} converted successfully.")
    return ok == len(files)


# ------------------------------------------------------------------- GUI

def run_gui() -> None:
    """Tiny window: pick a file and a format, then convert next to the original."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ImportError:
        print("Error: tkinter is not available in this Python installation.")
        v = sys.version_info
        print(f"On macOS with Homebrew, install it with: brew install python-tk@{v.major}.{v.minor}")
        sys.exit(1)

    title = "PDF Converter"
    root = tk.Tk()
    root.title(title)
    root.resizable(False, False)
    selected = tk.StringVar(value="No file chosen")
    fmt = tk.StringVar(value="docx")

    def choose():
        patterns = " ".join(f"*{e}" for e in [".pdf", *sorted(IMAGE_EXTS)])
        path = filedialog.askopenfilename(filetypes=[("PDF or image", patterns)])
        if path:
            selected.set(path)
            fmt.set("pdf" if is_image(Path(path)) else "docx")

    def convert():
        src = Path(selected.get())
        if not src.is_file():
            messagebox.showwarning(title, "Please choose a file first.")
            return
        ask = lambda existing: messagebox.askyesno(title, f"{existing[0].name} already exists. Overwrite?")
        root.config(cursor="watch")
        root.update()
        ok = convert_file(src, target=fmt.get(), ask=ask)
        root.config(cursor="")
        if ok:
            messagebox.showinfo(title, f"Done. Saved next to:\n{src}")
        else:
            messagebox.showerror(title, "Conversion failed or was skipped. See the terminal for details.")

    tk.Label(root, textvariable=selected, width=55, anchor="w").pack(padx=10, pady=(10, 5))
    row = tk.Frame(root)
    row.pack(fill="x", padx=10, pady=10)
    tk.Button(row, text="Choose file", command=choose).pack(side="left")
    tk.Label(row, text="  Convert to:").pack(side="left")
    tk.OptionMenu(row, fmt, *PDF_TARGETS, "pdf").pack(side="left")
    tk.Button(row, text="Convert", command=convert).pack(side="right")
    root.mainloop()


# ------------------------------------------------------------------- CLI

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert PDFs to DOCX, TXT, PNG or JPG, and images to PDF. Runs fully offline.")
    parser.add_argument("input", nargs="?", help="PDF or image file to convert")
    parser.add_argument("output", nargs="?", help="output path (default: next to the input)")
    parser.add_argument("--to", choices=[*PDF_TARGETS, "pdf"],
                        help="output format (default: docx for PDFs, pdf for images)")
    parser.add_argument("--folder", help="convert every PDF (or image, with --to pdf) in this folder")
    parser.add_argument("--combine", action="store_true", help="with --folder --to pdf: merge all images into one PDF")
    parser.add_argument("--pages", help="only these pages, e.g. 1-3,5 (PDF input only)")
    parser.add_argument("--dpi", type=int, default=150, help="image resolution for png/jpg (default: 150)")
    parser.add_argument("--overwrite", action="store_true", help="replace existing files without asking")
    parser.add_argument("--gui", action="store_true", help="open a small graphical window")
    args = parser.parse_args()

    if args.gui:
        run_gui()
    elif args.folder:
        if args.input:
            parser.error("use either a single file or --folder, not both")
        ok = convert_folder(Path(args.folder), args.to, args.pages, args.dpi, args.overwrite, args.combine)
        sys.exit(0 if ok else 1)
    elif args.input:
        ok = convert_file(args.input, args.output, args.to, args.pages, args.dpi, args.overwrite)
        sys.exit(0 if ok else 1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
