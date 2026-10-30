"""Offline tests: loaders (all formats), vector store, RAG retrieval, chat store, theme contrast."""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import pytest

from fakes import FakeClient, fake_vec
from src import chat_store
from src.config import THEMES
from src.loaders import load_file
from src.rag import EmbeddingCache, add_document, build_messages, embed, format_context, retrieve
from src.vectorstore import VectorStore


def make_xlsx() -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame({"Region": ["North", "South", "North", "East"], "Sales": [100, 250.5, 300, 80],
                      "Date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-02-01", "2026-02-03"])}).to_excel(w, sheet_name="Sales", index=False)
        pd.DataFrame({"Name": ["Ann", "Bo"], "Role": ["Lead", "Dev"]}).to_excel(w, sheet_name="Team", index=False)
    return buf.getvalue()


def make_docx() -> bytes:
    from docx import Document
    d = Document()
    d.add_heading("Quarterly Report", 1)
    d.add_paragraph("Revenue grew strongly in the northern region this quarter.")
    t = d.add_table(rows=3, cols=2)
    for r, (a, b) in enumerate([("Item", "Cost"), ("Server", "1200"), ("License", "300")]):
        t.cell(r, 0).text, t.cell(r, 1).text = a, b
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def make_pptx() -> bytes:
    from pptx import Presentation
    p = Presentation()
    s = p.slides.add_slide(p.slide_layouts[1])
    s.shapes.title.text = "Roadmap"
    s.placeholders[1].text = "Launch the beta in March"
    buf = io.BytesIO()
    p.save(buf)
    return buf.getvalue()


def make_pdf(text="Hello from the PDF about refund policy") -> bytes:
    stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = "%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF"
    return out.encode()


def test_excel_loader():
    d = load_file("report.xlsx", make_xlsx())
    assert set(d.tables) == {"Sales", "Team"} and d.unit_label == "sheets" and d.units == 2
    summary = next(s for s in d.segments if s.loc == "Sales · summary")
    assert "sum=730.50" in summary.text and "North x2" in summary.text
    assert any("Region: North; Sales: 100" in s.text for s in d.segments)
    assert any(s.loc == "Sales · full table" for s in d.segments)


def test_docx_pptx_pdf_csv_txt_json():
    assert "Table 1" in load_file("a.docx", make_docx()).tables
    assert any("Launch the beta" in s.text for s in load_file("a.pptx", make_pptx()).segments)
    pdf = load_file("a.pdf", make_pdf())
    assert pdf.unit_label == "pages" and "refund policy" in pdf.segments[0].text and pdf.segments[0].loc == "p. 1"
    csv = load_file("data.csv", b"a,b\n1,2\n3,4\n")
    assert list(csv.tables["data"].columns) == ["a", "b"]
    tsv = load_file("data.tsv", b"a\tb\n1\t2\n")
    assert len(tsv.tables["data"]) == 1
    assert load_file("n.md", b"# Title\n\nSome notes here.").segments[0].loc == "part 1"
    assert "x" in load_file("r.json", b'[{"x": 1}, {"x": 2}]').tables["r"].columns


def test_loader_errors():
    for name, data in [("a.xls", b"x"), ("a.exe", b"x"), ("empty.txt", b"   "), ("bad.pdf", b"not a pdf"), ("bad.xlsx", b"zip?")]:
        with pytest.raises(ValueError):
            load_file(name, data)


def test_vectorstore_search_mmr_remove():
    s = VectorStore()
    texts = ["refund policy thirty days", "refund policy thirty days copy", "shipping times europe", "cats and dogs"]
    s.add(texts, [{"source": "a" if i < 2 else "b", "loc": "p. 1", "role": "text"} for i in range(4)], [fake_vec(t) for t in texts])
    q = fake_vec("refund policy")
    plain = s.search(q, k=2, mmr=False)
    assert [h.text for h in plain][0].startswith("refund")
    diverse = s.search(q, k=2, mmr=True)
    assert diverse[0].text.startswith("refund") and diverse[1].text != plain[1].text or len(diverse) == 2
    assert {h.meta["source"] for h in s.search(q, k=4, allowed={"b"}, mmr=False)} <= {"b"}
    s.remove_source("a")
    assert len(s) == 2 and s.sources() == {"b": 2}


def test_rag_end_to_end_with_cache(tmp_path):
    client, cache, store = FakeClient(), EmbeddingCache(tmp_path / "e.sqlite"), VectorStore()
    doc = load_file("report.xlsx", make_xlsx())
    n = add_document(store, client, doc, 1000, 150, cache)
    assert n == len(store) and cache.count() == n
    calls = client.calls
    store2 = VectorStore()
    add_document(store2, client, doc, 1000, 150, cache)          # second upload: served from cache
    assert client.calls == calls
    hits = retrieve(store, client, "What is the total sales?", k=3, threshold=0.0, cache=cache)
    assert any(h.meta["role"] == "summary" for h in hits)        # numeric question pulls table summaries
    assert len(retrieve(store, client, "summarize", wide=True)) >= 3
    ctx = format_context(hits)
    msgs = build_messages("You are helpful.", ctx, [], "total?")
    assert msgs[0].type == "system" and "[1]" in msgs[0].content and msgs[-1].content == "total?"
    assert build_messages("You are helpful.", "", [], "hi")[0].content == "You are helpful."


def test_chat_store_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_store, "CHATS_FILE", tmp_path / "c.json")
    monkeypatch.setattr(chat_store, "PERSIST", True)
    c = chat_store.new_chat()
    c["messages"] = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo", "sources": [{"source": "f", "loc": "p. 1"}]}]
    chat_store.save({"id1": c, "empty": chat_store.new_chat()})
    loaded = chat_store.load()
    assert list(loaded) == ["id1"] and loaded["id1"]["messages"][0]["content"] == "hi"
    assert "[1] f · p. 1" in chat_store.export_markdown(c)


def _lum(h):
    h = h.lstrip("#")
    f = lambda c: c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
    r, g, b = (f(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    return .2126 * r + .7152 * g + .0722 * b


def test_theme_contrast():
    cr = lambda a, b: (max(_lum(a), _lum(b)) + .05) / (min(_lum(a), _lum(b)) + .05)
    for name, t in THEMES.items():
        bgs = [t["bg1"], t["bg2"], t["bg3"], t["field"]]
        assert min(cr(t["text"], b) for b in bgs) >= 4.5, name
        assert min(cr(t["muted"], b) for b in bgs) >= 4.5, name
        assert cr(t["onacc"], t["accent"]) >= 4.5, name
