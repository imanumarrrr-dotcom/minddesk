"""Turn uploaded files (PDF, Word, PowerPoint, Excel, CSV, text, JSON) into searchable segments + tables."""
from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import PurePath

import pandas as pd

MAX_ROWS_LOADED = 50_000   # rows kept for the Data explorer
MAX_ROWS_INDEXED = 5_000   # rows turned into searchable text per sheet
ROWS_PER_SEGMENT = 25
FULL_TABLE_ROWS, FULL_TABLE_CHARS = 200, 6000


@dataclass
class Segment:
    text: str
    loc: str            # human readable location: "p. 3", "slide 2", "Sales · rows 1-25"
    role: str = "text"  # "summary" segments are never split and are pulled in for numeric questions


@dataclass
class LoadedDoc:
    name: str
    kind: str
    unit_label: str = "parts"
    units: int = 0
    segments: list = field(default_factory=list)
    tables: dict = field(default_factory=dict)  # label -> DataFrame
    warnings: list = field(default_factory=list)

    @property
    def chars(self) -> int:
        return sum(len(s.text) for s in self.segments)


def _fmt(v) -> str:
    if v is None or (pd.api.types.is_scalar(v) and pd.isna(v)):
        return ""
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.strftime("%Y-%m-%d") if (v.hour, v.minute, v.second) == (0, 0, 0) else v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:.6g}"
    return str(v).strip()


def _clean(df: pd.DataFrame, doc: LoadedDoc, label: str) -> pd.DataFrame:
    df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    df.columns = [str(c).strip() for c in df.columns]
    if len(df) > MAX_ROWS_LOADED:
        doc.warnings.append(f"'{label}' has {len(df):,} rows; only the first {MAX_ROWS_LOADED:,} were loaded.")
        df = df.head(MAX_ROWS_LOADED)
    return df


def profile_text(label: str, df: pd.DataFrame) -> str:
    """Deterministic table summary so totals / averages are answerable without reading every row."""
    lines = [f"Summary of table '{label}': {len(df):,} rows x {len(df.columns)} columns.",
             "Columns: " + ", ".join(f"{c} ({df[c].dtype})" for c in df.columns)]
    for c in df.select_dtypes("number").columns[:25]:
        s = df[c].dropna()
        if len(s):
            lines.append(f"- {c}: sum={s.sum():,.2f}, mean={s.mean():,.2f}, min={s.min():,.2f}, max={s.max():,.2f}, count={len(s)}")
    for c in df.select_dtypes(include=["datetime", "datetimetz"]).columns[:5]:
        s = df[c].dropna()
        if len(s):
            lines.append(f"- {c}: from {_fmt(s.min())} to {_fmt(s.max())}")
    for c in df.select_dtypes(exclude=["number", "datetime", "datetimetz"]).columns[:15]:
        s = df[c].dropna().astype(str)
        if 0 < s.nunique() <= 30:
            lines.append(f"- {c} (top values): " + ", ".join(f"{k} x{v}" for k, v in s.value_counts().head(8).items()))
    missing = df.isna().sum()
    missing = missing[missing > 0]
    if len(missing):
        lines.append("Missing values: " + ", ".join(f"{k}={v}" for k, v in missing.head(15).items()))
    return "\n".join(lines)[:3500]


def table_segments(label: str, df: pd.DataFrame, doc: LoadedDoc) -> list:
    segs = [Segment(profile_text(label, df), f"{label} · summary", "summary")]
    small = df.head(FULL_TABLE_ROWS).to_csv(index=False)
    if len(df) <= FULL_TABLE_ROWS and len(small) <= FULL_TABLE_CHARS:
        segs.append(Segment(f"Full table '{label}' (CSV):\n{small}", f"{label} · full table", "summary"))
    rows = df.head(MAX_ROWS_INDEXED)
    if len(df) > MAX_ROWS_INDEXED:
        doc.warnings.append(f"'{label}': only the first {MAX_ROWS_INDEXED:,} rows were made searchable (summary covers all rows).")
    for start in range(0, len(rows), ROWS_PER_SEGMENT):
        block = rows.iloc[start:start + ROWS_PER_SEGMENT]
        lines = []
        for i, (_, r) in enumerate(block.iterrows(), start + 1):
            cells = "; ".join(f"{c}: {_fmt(v)}" for c, v in r.items() if _fmt(v))
            if cells:
                lines.append(f"[{label}] row {i}: {cells}")
        if lines:
            segs.append(Segment("\n".join(lines), f"{label} · rows {start + 1}-{start + len(block)}"))
    return segs


def text_segments(text: str, prefix: str = "part", limit: int = 2500) -> list:
    """Group paragraphs into ~limit-char parts."""
    parts, buf = [], ""
    for para in re.split(r"\n\s*\n", text.replace("\r", "")):
        para = para.strip()
        if not para:
            continue
        if buf and len(buf) + len(para) > limit:
            parts.append(buf)
            buf = ""
        buf = f"{buf}\n\n{para}".strip()
    if buf:
        parts.append(buf)
    return [Segment(p, f"{prefix} {i}") for i, p in enumerate(parts, 1)]


# ------------------------------------------------------------------ per-format loaders
def _pdf(doc: LoadedDoc, data: bytes) -> None:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        try:
            ok = reader.decrypt("")
        except Exception:
            ok = 0
        if not ok:
            raise ValueError("This PDF is password-protected. Remove the password and upload it again.")
    doc.unit_label, doc.units = "pages", len(reader.pages)
    for i, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        if text:
            doc.segments.append(Segment(text, f"p. {i}"))
    if not doc.segments:
        doc.warnings.append("No text layer found — this looks like a scanned PDF (OCR is not supported).")


def _docx(doc: LoadedDoc, data: bytes) -> None:
    from docx import Document
    d = Document(io.BytesIO(data))
    lines = []
    for p in d.paragraphs:
        t = p.text.strip()
        if t:
            lines.append(("# " if (p.style.name or "").lower().startswith("heading") else "") + t)
    doc.segments += text_segments("\n\n".join(lines), "section")
    doc.unit_label, doc.units = "sections", len(doc.segments)
    for n, tbl in enumerate(d.tables, 1):
        rows = [[c.text.strip() for c in r.cells] for r in tbl.rows]
        if len(rows) > 1:
            label = f"Table {n}"
            df = _clean(pd.DataFrame(rows[1:], columns=[c or f"col{i}" for i, c in enumerate(rows[0])]), doc, label)
            doc.tables[label] = df
            doc.segments += table_segments(label, df, doc)


def _pptx(doc: LoadedDoc, data: bytes) -> None:
    from pptx import Presentation
    prs = Presentation(io.BytesIO(data))
    doc.unit_label, doc.units = "slides", len(prs.slides)
    for i, slide in enumerate(prs.slides, 1):
        out = []
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip():
                out.append(shape.text_frame.text.strip())
            if getattr(shape, "has_table", False) and shape.has_table:
                out += [" | ".join(c.text.strip() for c in r.cells) for r in shape.table.rows]
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            out.append("Speaker notes: " + slide.notes_slide.notes_text_frame.text.strip())
        if out:
            doc.segments.append(Segment("\n".join(out), f"slide {i}"))


def _excel(doc: LoadedDoc, data: bytes) -> None:
    sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, engine="openpyxl")
    doc.unit_label = "sheets"
    for sheet, df in sheets.items():
        df = _clean(df, doc, sheet)
        if df.empty:
            continue
        doc.tables[str(sheet)] = df
        doc.segments += table_segments(str(sheet), df, doc)
    doc.units = len(doc.tables)


def _csv(doc: LoadedDoc, data: bytes, sep: str | None) -> None:
    df = None
    for enc in ("utf-8-sig", "latin-1"):
        for kwargs in (dict(sep=sep, engine="python"), dict(sep=sep or ",")):
            try:
                df = pd.read_csv(io.BytesIO(data), encoding=enc, **kwargs)
                break
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        if df is not None:
            break
    if df is None:
        raise ValueError("Could not parse this file as CSV.")
    label = PurePath(doc.name).stem
    df = _clean(df, doc, label)
    doc.unit_label, doc.units = "tables", 1
    doc.tables[label] = df
    doc.segments += table_segments(label, df, doc)


def _text(doc: LoadedDoc, data: bytes) -> None:
    doc.segments += text_segments(data.decode("utf-8", errors="replace"))
    doc.unit_label, doc.units = "parts", len(doc.segments)


def _json(doc: LoadedDoc, data: bytes) -> None:
    obj = json.loads(data.decode("utf-8-sig", errors="replace"))
    if isinstance(obj, list) and obj and all(isinstance(r, dict) for r in obj):
        label = PurePath(doc.name).stem
        df = _clean(pd.json_normalize(obj), doc, label)
        doc.unit_label, doc.units = "tables", 1
        doc.tables[label] = df
        doc.segments += table_segments(label, df, doc)
    else:
        doc.segments += text_segments(json.dumps(obj, indent=2, ensure_ascii=False), "part", 2000)
        doc.unit_label, doc.units = "parts", len(doc.segments)


def load_file(name: str, data: bytes) -> LoadedDoc:
    """Parse one uploaded file. Raises ValueError with a friendly message when it cannot be read."""
    ext = PurePath(name).suffix.lower().lstrip(".")
    doc = LoadedDoc(name=name, kind=ext)
    try:
        if ext == "pdf":
            _pdf(doc, data)
        elif ext == "docx":
            _docx(doc, data)
        elif ext == "pptx":
            _pptx(doc, data)
        elif ext in ("xlsx", "xlsm"):
            _excel(doc, data)
        elif ext == "csv":
            _csv(doc, data, None)
        elif ext == "tsv":
            _csv(doc, data, "\t")
        elif ext in ("txt", "md"):
            _text(doc, data)
        elif ext == "json":
            _json(doc, data)
        elif ext == "xls":
            raise ValueError("Old .xls files are not supported — save the workbook as .xlsx and upload again.")
        else:
            raise ValueError(f"Unsupported file type '.{ext}'.")
    except ValueError:
        raise
    except Exception as exc:  # corrupt / unexpected files
        raise ValueError(f"Could not read {name} ({type(exc).__name__}). The file may be corrupt.") from exc
    if not doc.segments:
        raise ValueError(f"No readable text was found in {name}.")
    return doc
