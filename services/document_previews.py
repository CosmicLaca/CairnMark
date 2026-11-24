"""Tool-independent previews for generated local documents."""

import csv
import html
import io
import json
import os
import threading
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from flask import current_app


class DocumentPreviewError(RuntimeError):
    """Raised when a generated document has no supported preview format."""


@dataclass(frozen=True)
class DocumentPreview:
    """Describe a cached preview response."""

    path: Path
    mimetype: str


class DocumentPreviewService:
    """Build safe cached previews without invoking the document's creator."""

    PREVIEW_VERSION = "2"
    HTML_SUFFIXES = frozenset({".csv", ".docx", ".json", ".md", ".odt", ".txt"})
    SUPPORTED_SUFFIXES = HTML_SUFFIXES | {".pdf"}
    _WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    _ODT_NAMESPACES = {
        "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
        "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
        "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    }

    def __init__(self):
        self._cache_lock = threading.Lock()

    def preview(self, source_path, relative_name):
        """Return a current preview, creating it only when missing or stale."""
        source = Path(source_path)
        relative_path = Path(relative_name)
        suffix = source.suffix.lower()
        if suffix not in self.SUPPORTED_SUFFIXES:
            raise DocumentPreviewError("This document type cannot be previewed.")
        if not source.is_file():
            raise DocumentPreviewError("The generated document no longer exists.")
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise DocumentPreviewError("Invalid generated document path.")

        if suffix == ".pdf":
            return DocumentPreview(source, "application/pdf")

        cache_root = Path(current_app.config["DOCUMENT_PREVIEW_DIRECTORY"])
        preview_path = cache_root / relative_path
        preview_path = preview_path.with_name(f"{preview_path.name}.html")
        with self._cache_lock:
            if not self._is_current(preview_path, source):
                preview_path.parent.mkdir(parents=True, exist_ok=True)
                self._create_preview(source, preview_path, suffix)
        return DocumentPreview(preview_path, "text/html")

    @classmethod
    def _is_current(cls, preview_path, source_path):
        current = (
            preview_path.is_file()
            and preview_path.stat().st_size > 0
            and preview_path.stat().st_mtime_ns >= source_path.stat().st_mtime_ns
        )
        if not current:
            return False
        try:
            header = preview_path.read_text(encoding="utf-8")[:512]
        except OSError:
            return False
        return f'content="{cls.PREVIEW_VERSION}"' in header

    def _create_preview(self, source_path, preview_path, suffix):
        temporary_path = preview_path.with_name(
            f".{preview_path.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            body = self._render_html_body(source_path, suffix)
            temporary_path.write_text(
                self._html_document(source_path.name, body),
                encoding="utf-8",
            )
            os.replace(temporary_path, preview_path)
        except (
            KeyError,
            OSError,
            ValueError,
            csv.Error,
            zipfile.BadZipFile,
            ElementTree.ParseError,
        ) as error:
            temporary_path.unlink(missing_ok=True)
            current_app.logger.warning(
                "Could not create preview for %s: %s", source_path.name, error
            )
            raise DocumentPreviewError(
                "The document preview could not be created."
            ) from error

    def _render_html_body(self, source_path, suffix):
        if suffix == ".docx":
            return self._render_docx(source_path)
        if suffix == ".odt":
            return self._render_odt(source_path)
        text = source_path.read_text(encoding="utf-8", errors="replace")
        if suffix == ".json":
            try:
                text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                pass
        if suffix == ".csv":
            return self._render_csv(text)
        return f"<pre>{html.escape(text)}</pre>"

    def _render_docx(self, source_path):
        namespace = {"w": self._WORD_NAMESPACE}
        qualified = lambda name: f"{{{self._WORD_NAMESPACE}}}{name}"
        with zipfile.ZipFile(source_path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        body = root.find("w:body", namespace)
        if body is None:
            return "<p>No previewable content.</p>"

        blocks = []
        for child in body:
            if child.tag == qualified("p"):
                rendered = self._docx_paragraph(child, namespace, qualified)
                if rendered:
                    blocks.append(rendered)
            elif child.tag == qualified("tbl"):
                blocks.append(self._docx_table(child, namespace))
        return "".join(blocks) or "<p>No previewable content.</p>"

    @staticmethod
    def _docx_paragraph(paragraph, namespace, qualified):
        style_node = paragraph.find("w:pPr/w:pStyle", namespace)
        style = style_node.get(qualified("val"), "") if style_node is not None else ""
        parts = []
        for run in paragraph.findall(".//w:r", namespace):
            run_text = "".join(
                node.text or "" for node in run.findall(".//w:t", namespace)
            )
            if not run_text:
                continue
            escaped = html.escape(run_text)
            properties = run.find("w:rPr", namespace)
            if properties is not None:
                if properties.find("w:b", namespace) is not None:
                    escaped = f"<strong>{escaped}</strong>"
                if properties.find("w:i", namespace) is not None:
                    escaped = f"<em>{escaped}</em>"
                if properties.find("w:u", namespace) is not None:
                    escaped = f"<u>{escaped}</u>"
            parts.append(escaped)
        content = "".join(parts)
        if not content:
            return ""
        normalized_style = style.lower().replace(" ", "")
        if normalized_style == "title":
            return f"<h1>{content}</h1>"
        if normalized_style.startswith("heading"):
            level_text = normalized_style.removeprefix("heading")
            level = min(max(int(level_text or "2"), 1), 6)
            return f"<h{level}>{content}</h{level}>"
        if paragraph.find("w:pPr/w:numPr", namespace) is not None:
            return f'<div class="list-item">{content}</div>'
        return f"<p>{content}</p>"

    @staticmethod
    def _docx_table(table, namespace):
        rows = []
        for row_index, row in enumerate(table.findall("w:tr", namespace)):
            cells = []
            tag = "th" if row_index == 0 else "td"
            for cell in row.findall("w:tc", namespace):
                text = " ".join(
                    node.text or "" for node in cell.findall(".//w:t", namespace)
                ).strip()
                cells.append(f"<{tag}>{html.escape(text)}</{tag}>")
            if cells:
                rows.append(f"<tr>{''.join(cells)}</tr>")
        return f"<table>{''.join(rows)}</table>" if rows else ""

    def _render_odt(self, source_path):
        namespaces = self._ODT_NAMESPACES
        with zipfile.ZipFile(source_path) as archive:
            root = ElementTree.fromstring(archive.read("content.xml"))
        text_root = root.find(".//office:body/office:text", namespaces)
        if text_root is None:
            return "<p>No previewable content.</p>"
        blocks = []
        for node in text_root.iter():
            local_name = node.tag.rsplit("}", 1)[-1]
            if local_name not in {"h", "p"}:
                continue
            content = html.escape("".join(node.itertext()).strip())
            if not content:
                continue
            if local_name == "h":
                level_key = f"{{{namespaces['text']}}}outline-level"
                level = min(max(int(node.get(level_key, "2")), 1), 6)
                blocks.append(f"<h{level}>{content}</h{level}>")
            else:
                blocks.append(f"<p>{content}</p>")
        return "".join(blocks) or "<p>No previewable content.</p>"

    @staticmethod
    def _render_csv(text):
        rows = list(csv.reader(io.StringIO(text)))
        rendered_rows = []
        for row_index, row in enumerate(rows[:250]):
            tag = "th" if row_index == 0 else "td"
            cells = "".join(f"<{tag}>{html.escape(value)}</{tag}>" for value in row)
            rendered_rows.append(f"<tr>{cells}</tr>")
        return f"<table>{''.join(rendered_rows)}</table>"

    @staticmethod
    def _html_document(filename, body):
        safe_name = html.escape(filename)
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="cairnmark-preview-version" content="2">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_name}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 10px; color: #202925; background: #eef1ee;
    font: 14px/1.55 Georgia, 'Times New Roman', serif; }}
  main {{ min-height: calc(100vh - 20px); max-width: 820px; margin: auto; padding: 24px 28px;
    background: #fff; box-shadow: 0 4px 20px rgba(24, 37, 32, .13); }}
  .preview-note {{ margin: -12px 0 28px; color: #64716c; font: 11px/1.4 system-ui, sans-serif; }}
  h1, h2, h3, h4, h5, h6 {{ color: #174f47; line-height: 1.2; }}
  h1 {{ margin-top: 0; font-size: 27px; }}
  p {{ margin: 0 0 1em; }}
  .list-item {{ margin: 0 0 .35em 1.2em; }}
  .list-item::before {{ content: '•'; margin-left: -1em; margin-right: .55em; }}
  table {{ width: 100%; margin: 18px 0; border-collapse: collapse; font: 12px/1.4 system-ui, sans-serif; }}
  th, td {{ padding: 7px 9px; border: 1px solid #b7c7c1; text-align: left; vertical-align: top; }}
  th {{ color: #fff; background: #256b60; }}
  tr:nth-child(even) td {{ background: #edf7f4; }}
  pre {{ margin: 0; overflow-wrap: anywhere; white-space: pre-wrap; font: 12px/1.5 Consolas, monospace; }}
</style>
</head>
<body><main><div class="preview-note">Quick preview · download the original for exact formatting</div>{body}</main></body>
</html>"""


DOCUMENT_PREVIEWS = DocumentPreviewService()
