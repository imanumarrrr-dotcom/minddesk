# 🪷 MindDesk — assistant + document RAG in one calm workspace

MindDesk merges **Custom ChatGPT** (multi-chat, personas, streaming) with a **RAG agent** and extends it to
**PDF, Word, PowerPoint, Excel, CSV/TSV, TXT/Markdown and JSON**. Theme: Ice Silver `#DDE3E8` · Deep Aubergine `#3A0F34` · Marigold `#EAAA00`.

## Features
- 🔐 API-key gate: the workspace unlocks only after OpenAI verifies your key (kept in session memory, never written to disk)
- 💬 Chat: multiple chats, search, persona + editable system role per chat, streaming answers, export to Markdown
- 📚 Knowledge (RAG): upload many files, per-file on/off, citations `[1] file · p. 3`, MMR + relevance threshold, evenly-sampled summaries
- 📗 Excel/CSV aware: each sheet gets a deterministic summary (sums, means, top values) so numeric questions are answered from real figures,
  small tables are included whole, and rows are searchable
- 📊 Data explorer: themed table preview, column stats, chart builder (bar/line/scatter/histogram/pie/box), CSV download, "Ask AI to analyse"
- 🛠 Studio: retrieval inspector, prompt preview, index + cache stats
- 🎨 3 animated themes (Ice Silver, Deep Aubergine, Marigold): colours cross-fade and a wipe sweeps the screen on every switch
- ⚡ Embedding cache (SQLite): re-uploading a file costs no API calls

## Run
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
Python 3.10–3.12 recommended. Optional `.env` (see `.env.example`).

## Deploy (Streamlit Cloud)
Push **everything**: `app.py`, `requirements.txt`, the `src/` folder (with `__init__.py`) and `.streamlit/`. Set `MINDDESK_PERSIST=0`
in the app's secrets/env so chats and embeddings are not stored on the shared server. Never commit `.env`.

## Structure
```
app.py                UI (gate, chat, knowledge, data, studio)
src/config.py         models, personas, file types, themes
src/loaders.py        PDF / DOCX / PPTX / XLSX / CSV / TXT / JSON -> segments + tables
src/rag.py            chunking, embeddings + SQLite cache, retrieval, prompts
src/vectorstore.py    NumPy cosine search + MMR
src/llm.py            ChatOpenAI helpers, key validation, streaming
src/chat_store.py     chat history (JSON), export
src/theme.py          animated CSS themes
tests/                offline tests (no API key needed):  pytest tests
```

## Notes
- Scanned PDFs (images only) have no text layer; OCR is not included. Old `.xls` must be saved as `.xlsx`.
- Answers about spreadsheets use only the figures shown in the context; very large sheets are summarised over all rows but only the first 5,000 rows are searchable.
