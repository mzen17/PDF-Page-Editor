# PDF Page Editor (Barebones)

A minimal Tkinter app to import PDF pages, reorder them with drag-and-drop (single or multi-select), toggle inclusion per page, and export a new PDF.

## Features
- Import one or more PDFs; all pages show as thumbnails in a horizontal strip
- Selection: single click, Ctrl/Cmd-click to toggle, Shift-click for range
- Drag and drop to reorder selected pages (multi-select drag supported)
- Include checkbox per page (default on) controls export content
- Export selected pages in the current order into a new PDF

## Requirements
- Python 3.8+
- Linux, macOS, or Windows

Python packages:
- pymupdf (render thumbnails)
- pillow (image handling)
- pypdf (PDF writing)

Install with:

```bash
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python gui.py
```

## Notes
- Thumbnails are generated at import time; large PDFs may take a moment.
- Export requires at least one included page.
- If you have very large PDFs, consider running from a terminal to see status messages.