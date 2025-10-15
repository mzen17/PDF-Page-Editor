from __future__ import annotations
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from dataclasses import dataclass
from typing import List, Optional, Tuple, Any

# Third-party libraries:
# - pymupdf (fitz) for rendering PDF thumbnails
# - pillow (PIL) for Tk-compatible images
# - pypdf for assembling/exporting the PDF
try:
	import fitz  # pymupdf
except Exception:  # pragma: no cover - runtime helpful message
	fitz = None

try:
	from PIL import Image, ImageTk
except Exception:
	Image = None
	ImageTk = None

try:
	from pypdf import PdfReader, PdfWriter
except Exception:
	PdfReader = None
	PdfWriter = None


THUMBNAIL_MAX_WIDTH = 180
THUMBNAIL_MAX_HEIGHT = 240
PAGE_FRAME_PADX = 8


@dataclass
class PageItem:
	source_path: str
	page_index: int
	image: Any  # PIL Image
	photo: Any  # ImageTk.PhotoImage
	include_var: tk.BooleanVar


class ScrollableRow(tk.Frame):
	"""A horizontally-scrollable row of widgets using a Canvas + inner Frame.

	Children should be added to self.inner using grid(column=i, row=0).
	"""

	def __init__(self, master, height=320, **kwargs):
		super().__init__(master, **kwargs)
		self.canvas = tk.Canvas(self, height=height, highlightthickness=0)
		self.hbar = tk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.canvas.xview)
		self.canvas.configure(xscrollcommand=self.hbar.set)

		self.inner = tk.Frame(self.canvas)
		self.window_id = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")

		self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
		self.hbar.pack(side=tk.BOTTOM, fill=tk.X)

		self.inner.bind("<Configure>", self._on_frame_configure)
		self.canvas.bind("<Configure>", self._on_canvas_configure)

		# Enable horizontal mouse wheel scrolling (Shift+Wheel)
		self.canvas.bind_all("<Shift-MouseWheel>", self._on_mousewheel)

	def _on_frame_configure(self, _event=None):
		bbox = self.canvas.bbox(self.window_id)
		if bbox:
			self.canvas.configure(scrollregion=bbox)

	def _on_canvas_configure(self, event):
		# Keep inner frame height in sync with canvas height
		self.canvas.itemconfigure(self.window_id, height=event.height)

	def _on_mousewheel(self, event):
		# Negative for right on Windows, but we'll normalize across platforms
		delta = event.delta
		if sys.platform == "darwin":
			factor = 2
		else:
			factor = 1
		self.canvas.xview_scroll(int(-1 * (delta / 120) * factor), "units")


class PDFPageEditorApp(tk.Tk):
	def __init__(self):
		super().__init__()
		self.title("PDF Page Editor (Barebones)")
		self.geometry("1100x520")

		# State
		self.pages: List[PageItem] = []
		self.page_frames: List[tk.Frame] = []
		self.selected_indices: List[int] = []  # maintain order of selection
		self.last_clicked_index: Optional[int] = None

		# Drag state
		self.dragging: bool = False
		self.drag_start_index: Optional[int] = None
		self.drop_index: Optional[int] = None
		self.insert_bar: Optional[tk.Frame] = None

		# UI
		self._build_toolbar()
		self.row = ScrollableRow(self, height=360)
		self.row.pack(fill=tk.BOTH, expand=True)

		self.status = tk.StringVar(value="Ready")
		tk.Label(self, textvariable=self.status, anchor="w").pack(fill=tk.X)

		self._check_dependencies()

	# ---------- UI construction ----------
	def _build_toolbar(self):
		bar = tk.Frame(self)
		bar.pack(fill=tk.X, pady=4)

		tk.Button(bar, text="Add PDFs", command=self.on_add_pdfs).pack(side=tk.LEFT, padx=4)
		tk.Button(bar, text="Export...", command=self.on_export).pack(side=tk.LEFT, padx=4)

		tk.Label(bar, text="Hint: Shift = range select, Ctrl/Cmd = toggle select, drag to reorder", fg="#555").pack(side=tk.LEFT, padx=12)

	def _check_dependencies(self):
		missing = []
		if fitz is None:
			missing.append("pymupdf")
		if Image is None or ImageTk is None:
			missing.append("pillow")
		if PdfReader is None or PdfWriter is None:
			missing.append("pypdf")
		if missing:
			self.status.set("Missing dependencies: " + ", ".join(missing) + ". See README to install.")

	# ---------- Page management ----------
	def on_add_pdfs(self):
		file_paths = filedialog.askopenfilenames(
			title="Select PDF files",
			filetypes=[("PDF files", "*.pdf")],
		)
		if not file_paths:
			return
		try:
			self._import_pdfs(file_paths)
			self.status.set(f"Loaded {len(file_paths)} file(s), total pages: {len(self.pages)}")
		except Exception as e:
			messagebox.showerror("Error", f"Failed to import PDFs:\n{e}")

	def _import_pdfs(self, file_paths: Tuple[str, ...]):
		for path in file_paths:
			if fitz is None:
				raise RuntimeError("pymupdf not installed")
			doc = fitz.open(path)
			for page_index in range(len(doc)):
				page = doc.load_page(page_index)
				pix = page.get_pixmap(matrix=self._thumbnail_matrix(page))
				mode = "RGB" if pix.alpha == 0 else "RGBA"
				pil_img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
				photo = ImageTk.PhotoImage(pil_img)
				item = PageItem(
					source_path=path,
					page_index=page_index,
					image=pil_img,
					photo=photo,
					include_var=tk.BooleanVar(value=True),
				)
				self.pages.append(item)
				self._create_page_frame(len(self.pages) - 1)
			doc.close()
		self._layout_page_frames()

	def _thumbnail_matrix(self, page):
		# Compute scale to fit within the thumbnail max dimensions
		rect = page.rect
		width, height = rect.width, rect.height
		scale = min(THUMBNAIL_MAX_WIDTH / width, THUMBNAIL_MAX_HEIGHT / height)
		if scale <= 0:
			scale = 0.2
		return fitz.Matrix(scale, scale)

	def _create_page_frame(self, index: int):
		item = self.pages[index]
		frame = tk.Frame(self.row.inner, bd=2, relief=tk.RIDGE, bg="#f8f9fa")

		thumb = tk.Label(frame, image=item.photo, bg="#ffffff")
		thumb.image = item.photo  # keep reference
		thumb.pack(padx=6, pady=6)

		info = tk.Frame(frame, bg="#f8f9fa")
		info.pack(fill=tk.X, padx=6, pady=(0, 6))

		tk.Checkbutton(
			info,
			text=f"Include p{item.page_index + 1}",
			variable=item.include_var,
			bg="#f8f9fa",
		).pack(side=tk.LEFT)

		# Bind interactions to both frame and thumb for convenience
		for w in (frame, thumb):
			w.bind("<Button-1>", lambda e, fr=frame: self._on_click(e, fr))
			w.bind("<B1-Motion>", lambda e, fr=frame: self._on_drag(e, fr))
			w.bind("<ButtonRelease-1>", lambda e, fr=frame: self._on_release(e, fr))

		self.page_frames.append(frame)

	def _layout_page_frames(self):
		# Clear existing grid
		for i, f in enumerate(self.page_frames):
			f.grid_forget()
		# Re-grid in current order
		for i, f in enumerate(self.page_frames):
			f.grid(row=0, column=i, padx=PAGE_FRAME_PADX, pady=8, sticky="n")
		self.row.inner.update_idletasks()
		self._refresh_selection_visuals()

	# ---------- Selection logic ----------
	def _on_click(self, event, frame: tk.Widget):
		# Resolve index from the frame at click-time so it's accurate after reorders
		index = self._index_from_frame_or_child(frame)
		# Determine modifier keys
		ctrl = (event.state & 0x0004) != 0 or (sys.platform == "darwin" and (event.state & 0x0008) != 0)
		shift = (event.state & 0x0001) != 0

		if shift and self.last_clicked_index is not None:
			start = min(self.last_clicked_index, index)
			end = max(self.last_clicked_index, index)
			self.selected_indices = list(range(start, end + 1))
		elif ctrl:
			if index in self.selected_indices:
				self.selected_indices.remove(index)
			else:
				self.selected_indices.append(index)
			self.selected_indices.sort()
			self.last_clicked_index = index
		else:
			self.selected_indices = [index]
			self.last_clicked_index = index

		self._refresh_selection_visuals()

		# Prepare for potential drag
		self.dragging = False
		self.drag_start_index = index
		self.drop_index = None

	def _refresh_selection_visuals(self):
		for i, frame in enumerate(self.page_frames):
			if i in self.selected_indices:
				frame.configure(bg="#e7f5ff", bd=3, relief=tk.SOLID)
			else:
				frame.configure(bg="#f8f9fa", bd=2, relief=tk.RIDGE)

	# ---------- Drag and drop ----------
	def _on_drag(self, event, frame: tk.Widget):
		if self.drag_start_index is None:
			return
		# Start drag after small movement threshold
		self.dragging = True
		# Compute drop index based on cursor x over the inner frame
		x_root = event.x_root
		inner_left = self.row.inner.winfo_rootx()
		x_in_inner = x_root - inner_left
		self.drop_index = self._compute_drop_index(x_in_inner)
		self._show_insert_bar(self.drop_index)

	def _compute_drop_index(self, x_in_inner: int) -> int:
		# Find insertion position among frames by comparing x to midpoints
		positions = []
		for i, f in enumerate(self.page_frames):
			f.update_idletasks()
			x = f.winfo_x()
			w = f.winfo_width()
			positions.append((i, x, w))

		if not positions:
			return 0

		for i, x, w in positions:
			mid = x + w / 2
			if x_in_inner < mid:
				return i
		return len(positions)

	def _show_insert_bar(self, index: int):
		# Create or move a thin vertical bar at insertion index
		if self.insert_bar is None:
			self.insert_bar = tk.Frame(self.row.inner, bg="#339af0", width=3)
			self.insert_bar.place(y=0, relheight=1)

		# Compute x position as left of target frame or after last
		if index >= len(self.page_frames):
			if self.page_frames:
				last = self.page_frames[-1]
				x = last.winfo_x() + last.winfo_width() + PAGE_FRAME_PADX
			else:
				x = 0
		else:
			x = self.page_frames[index].winfo_x() - int(PAGE_FRAME_PADX / 2)
			if x < 0:
				x = 0
		self.insert_bar.place_configure(x=x)

	def _hide_insert_bar(self):
		if self.insert_bar is not None:
			self.insert_bar.place_forget()
			self.insert_bar.destroy()
			self.insert_bar = None

	def _on_release(self, _event, frame: tk.Widget):
		if not self.dragging or self.drop_index is None:
			return

		self._hide_insert_bar()

		# Build list of selected indices and pages
		sel = sorted(self.selected_indices)
		if not sel:
			return

		# Compute destination index adjusted for removals
		dest = self.drop_index
		# If moving items from before dest, removing them shifts dest left
		removed_before = sum(1 for i in sel if i < dest)
		dest -= removed_before
		if dest < 0:
			dest = 0

		# Extract selected items
		pages_to_move = [self.pages[i] for i in sel]
		frames_to_move = [self.page_frames[i] for i in sel]

		# Remove from current lists (delete from highest to lowest index)
		for i in reversed(sel):
			del self.pages[i]
			f = self.page_frames.pop(i)
			f.grid_forget()

		# Insert at destination preserving order
		for offset, (p, f) in enumerate(zip(pages_to_move, frames_to_move)):
			self.pages.insert(dest + offset, p)
			self.page_frames.insert(dest + offset, f)

		# Rebuild grid and selection indices
		self._layout_page_frames()

		# New indices of the moved pages are range(dest, dest+len(sel))
		self.selected_indices = list(range(dest, dest + len(sel)))
		self._refresh_selection_visuals()

		# Reset drag state
		self.dragging = False
		self.drag_start_index = None
		self.drop_index = None

	def _index_from_frame_or_child(self, widget: tk.Widget) -> int:
		# Walk up parents until we find the page frame
		current = widget
		while current is not None and current not in self.page_frames:
			try:
				current = current.master
			except Exception:
				break
		if current in self.page_frames:
			return self.page_frames.index(current)
		return -1

	# ---------- Export ----------
	def on_export(self):
		if not self.pages:
			messagebox.showinfo("Export", "No pages to export.")
			return
		if PdfReader is None or PdfWriter is None:
			messagebox.showerror("Missing dependency", "pypdf is required for export. See README.")
			return

		out_path = filedialog.asksaveasfilename(
			defaultextension=".pdf",
			filetypes=[("PDF files", "*.pdf")],
			title="Save exported PDF as...",
		)
		if not out_path:
			return

		try:
			self._export_pdf(out_path)
			self.status.set(f"Exported to {out_path}")
		except Exception as e:
			messagebox.showerror("Export failed", f"Could not export PDF:\n{e}")

	def _export_pdf(self, out_path: str):
		writer = PdfWriter()

		# Cache readers by source path
		readers = {}

		for item in self.pages:
			if not item.include_var.get():
				continue
			if item.source_path not in readers:
				readers[item.source_path] = PdfReader(item.source_path)
			reader = readers[item.source_path]
			writer.add_page(reader.pages[item.page_index])

		if len(writer.pages) == 0:
			raise RuntimeError("No pages selected for export.")

		with open(out_path, "wb") as f:
			writer.write(f)


def main():
	app = PDFPageEditorApp()
	app.mainloop()


if __name__ == "__main__":
	main()

