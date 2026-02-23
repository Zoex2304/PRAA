from __future__ import annotations

from pathlib import Path

_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"})
_TEXT_EXTS = frozenset({".txt", ".md"})
_PDF_EXTS = frozenset({".pdf"})
_DOCX_EXTS = frozenset({".docx"})


class FileTextExtractor:
    def is_image(self, path: Path) -> bool:
        return path.suffix.lower() in _IMAGE_EXTS

    def is_supported(self, path: Path) -> bool:
        return path.suffix.lower() in (
            _IMAGE_EXTS | _TEXT_EXTS | _PDF_EXTS | _DOCX_EXTS
        )

    def extract_text(self, path: Path) -> str:
        ext = path.suffix.lower()
        if ext in _TEXT_EXTS:
            return path.read_text(encoding="utf-8", errors="replace")
        if ext in _PDF_EXTS:
            return self._extract_pdf(path)
        if ext in _DOCX_EXTS:
            return self._extract_docx(path)
        raise ValueError(f"Unsupported format: {ext}")

    def _extract_pdf(self, path: Path) -> str:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _extract_docx(self, path: Path) -> str:
        from docx import Document

        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
