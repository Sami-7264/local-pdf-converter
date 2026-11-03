# Local PDF Converter

A small, offline command-line tool (with an optional mini GUI) for converting PDFs to Word, text and images, and images back to PDF.

All conversion runs on your own computer. Files are never uploaded anywhere, so it's safe for private documents.

## Features

| From | To | Notes |
|------|----|-------|
| PDF | **DOCX** (Word) | Keeps text, paragraphs and tables editable. Uses [pdf2docx](https://github.com/ArtifexSoftware/pdf2docx). |
| PDF | **TXT** | Plain text, pages separated by a blank line |
| PDF | **PNG / JPG** | One image per page, adjustable resolution (`--dpi`) |
| Images | **PDF** | PNG, JPG, BMP, GIF, TIFF. Convert one by one, or merge a whole folder into one PDF (`--combine`) |

Also included:

- **Page selection** (`--pages 1-3,5`) for any PDF conversion
- **Folder mode**: convert every file in a folder in one go
- **Clear messages** for missing files, invalid or corrupt PDFs, password-protected PDFs and bad page ranges
- **Overwrite protection**: asks before replacing an existing file, or use `--overwrite`
- **Scanned-PDF warning** when a PDF has no extractable text
- **Optional GUI** built with tkinter: choose a file, pick a format, convert

## Quick start

Requires **Python 3.10+**.

### macOS / Linux

```bash
git clone https://github.com/Sami-7264/local-pdf-converter.git
cd local-pdf-converter
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Windows (PowerShell)

```powershell
git clone https://github.com/Sami-7264/local-pdf-converter.git
cd local-pdf-converter
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

The first install downloads about 150 MB, mostly OpenCV, which pdf2docx uses for layout detection.

## Usage

```bash
# PDF -> Word (default). Saves report.docx next to report.pdf
python convert.py report.pdf
python convert.py report.pdf ~/Desktop/report.docx

# PDF -> plain text, pages 2 to 4 only
python convert.py report.pdf --to txt --pages 2-4

# PDF -> one PNG per page (report_p1.png, report_p2.png, ...)
python convert.py report.pdf --to png --dpi 200

# Image -> PDF
python convert.py photo.jpg

# Every PDF in a folder -> DOCX
python convert.py --folder ./pdfs

# Every image in a folder -> one combined PDF (./scans/scans.pdf)
python convert.py --folder ./scans --to pdf --combine

# Graphical window
python convert.py --gui
```

### All options

| Option | Description |
|--------|-------------|
| `input` | PDF or image to convert |
| `output` | Output path (optional; default is next to the input with a new extension) |
| `--to {docx,txt,png,jpg,pdf}` | Output format. Default is `docx` for PDFs and `pdf` for images. If you give an output path, its extension is used. |
| `--pages 1-3,5` | Convert only these pages. `3-` means page 3 to the end. |
| `--dpi N` | Image resolution for PNG/JPG output (default 150) |
| `--folder DIR` | Convert every PDF in `DIR`, or every image with `--to pdf`. Subfolders are not included. |
| `--combine` | With `--folder DIR --to pdf`, merge all images, in name order, into `DIR/<DIR>.pdf` |
| `--overwrite` | Replace existing output files without asking |
| `--gui` | Open the graphical window |

The exit code is `0` on success and `1` if anything failed or was skipped, so it works in scripts.

### Example output

```
$ python convert.py --folder ./pdfs
Found 3 file(s) in pdfs

Converting: pdfs/fake.pdf -> DOCX
  Error: Not a valid PDF file: pdfs/fake.pdf
Converting: pdfs/locked.pdf -> DOCX
  Error: PDF is password protected: pdfs/locked.pdf
Converting: pdfs/report.pdf -> DOCX
  Success: saved pdfs/report.docx

Done: 1 of 3 converted successfully.
```

## GUI

`python convert.py --gui` opens a small window with **Choose file**, a **Convert to** dropdown and a **Convert** button. The result is saved next to the original file.

tkinter ships with the python.org installers. If you use **Homebrew Python on macOS**, install it separately, matching your Python version:

```bash
brew install python-tk@3.14
```

On Debian or Ubuntu, run `sudo apt install python3-tk`.

## Limitations

- **Scanned PDFs**, where each page is just an image, have no real text. DOCX output will contain the page images and TXT output will be empty. Run OCR first, for example with [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF): `ocrmypdf scanned.pdf searchable.pdf`. Then convert the result.
- **Complex layouts** such as multi-column pages, floating text boxes, form fields, footnotes and unusual fonts may shift or need manual cleanup in Word.
- **Password-protected PDFs** are refused. Remove the password first, for example in Preview: File → Export as PDF without encryption.
- **Large PDFs** can be slow for DOCX output, at roughly a second or more per page.
- **Word → PDF** is not supported, because it needs Microsoft Word or LibreOffice installed.

## Project structure

```
convert.py        # the whole tool: CLI, converters and GUI
requirements.txt  # pdf2docx (also brings in PyMuPDF, python-docx and OpenCV)
```

## License

[MIT](LICENSE)
