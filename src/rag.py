"""Chunking, embeddings (with an on-disk cache), retrieval and prompt assembly."""
from __future__ import annotations

import hashlib
import re
import sqlite3
import time

import numpy as np
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import EMBED_MODEL
from .loaders import LoadedDoc
from .vectorstore import Hit, VectorStore

BATCH = 96
AGG_RE = re.compile(r"\b(total|sum|average|avg|mean|median|count|how many|max|min|highest|lowest|top|bottom|"
                    r"trend|growth|compare|percent|percentage|per|overall)\b|%", re.I)


class EmbeddingCache:
    """SQLite cache keyed by sha256(text): re-uploading a file costs nothing."""

    def __init__(self, path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(path), check_same_thread=False)
        self.con.execute("CREATE TABLE IF NOT EXISTS emb(h TEXT, model TEXT, v BLOB, PRIMARY KEY(h, model))")

    def get(self, h: str, model: str):
        row = self.con.execute("SELECT v FROM emb WHERE h=? AND model=?", (h, model)).fetchone()
        return np.frombuffer(row[0], dtype=np.float32) if row else None

    def put(self, h: str, model: str, v) -> None:
        self.con.execute("INSERT OR REPLACE INTO emb VALUES (?,?,?)", (h, model, np.asarray(v, np.float32).tobytes()))
        self.con.commit()

    def count(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM emb").fetchone()[0]


def _call(client, texts: list, model: str):
    last = None
    for attempt in range(4):
        try:
            return client.embeddings.create(model=model, input=texts)
        except Exception as exc:  # rate limit / timeout / connection: back off and retry
            last = exc
            if type(exc).__name__ not in ("RateLimitError", "APIConnectionError", "APITimeoutError", "InternalServerError"):
                raise
            time.sleep(2 ** attempt)
    raise last


def embed(client, texts: list, model: str = EMBED_MODEL, cache: EmbeddingCache | None = None, progress=None) -> np.ndarray:
    out: list = [None] * len(texts)
    need = []
    for i, t in enumerate(texts):
        h = hashlib.sha256(t.encode("utf-8")).hexdigest()
        v = cache.get(h, model) if cache else None
        if v is not None:
            out[i] = v
        else:
            need.append((i, h))
    for s in range(0, len(need), BATCH):
        batch = need[s:s + BATCH]
        resp = _call(client, [texts[i] for i, _ in batch], model)
        for (i, h), d in zip(batch, resp.data):
            out[i] = np.asarray(d.embedding, dtype=np.float32)
            if cache:
                cache.put(h, model, out[i])
        if progress:
            progress(min(s + BATCH, len(need)), len(need))
    return np.vstack(out)


def add_document(store: VectorStore, client, doc: LoadedDoc, size: int, overlap: int,
                 cache: EmbeddingCache | None = None, progress=None) -> int:
    """Split a loaded document, embed the chunks and add them to the store. Returns the chunk count."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=min(overlap, size // 2))
    texts, metas = [], []
    for seg in doc.segments:
        parts = [seg.text[:7000]] if seg.role == "summary" else splitter.split_text(seg.text)
        for p in parts:
            if p.strip():
                texts.append(p)
                metas.append({"source": doc.name, "loc": seg.loc, "kind": doc.kind, "role": seg.role})
    if not texts:
        raise ValueError(f"No text could be extracted from {doc.name}.")
    store.add(texts, metas, embed(client, texts, cache=cache, progress=progress))
    return len(texts)


def retrieve(store: VectorStore, client, question: str, prev_question: str = "", k: int = 4, mmr: bool = True,
             threshold: float = 0.15, allowed=None, wide: bool = False, cache=None) -> list[Hit]:
    if wide:
        return store.sample(14, allowed)
    query = f"{prev_question} {question}" if prev_question and len(question.split()) < 6 else question
    hits = store.search(embed(client, [query], cache=cache)[0], k=k, mmr=mmr, threshold=threshold, allowed=allowed)
    if AGG_RE.search(question):  # numeric questions: always include table summaries
        seen = {(h.meta["source"], h.meta["loc"]) for h in hits}
        extra = [h for h in store.profiles(allowed) if (h.meta["source"], h.meta["loc"]) not in seen]
        hits += extra[:3]
    return hits


# ------------------------------------------------------------------ prompts
RAG_SYSTEM = """{persona}

You have access to excerpts from the user's uploaded documents (PDF, Word, PowerPoint, Excel, CSV, text).
Rules:
- Prefer the CONTEXT below. Cite the excerpts you use as [1], [2] matching their numbers.
- If the context does not contain the answer, say so plainly, then you may add general knowledge clearly labelled as such.
- For spreadsheets and tables: never invent numbers. Use only the figures shown (the table summaries hold totals and averages).
  Show the arithmetic briefly when you compute something.
- Keep answers well structured (short paragraphs, bullets or small tables).

CONTEXT:
{context}"""

CHAT_PROMPT = ChatPromptTemplate.from_messages([("system", "{persona}"), MessagesPlaceholder("history"), ("human", "{question}")])
RAG_PROMPT = ChatPromptTemplate.from_messages([("system", RAG_SYSTEM), MessagesPlaceholder("history"), ("human", "{question}")])


def format_context(hits: list[Hit]) -> str:
    return "\n\n".join(f"[{i}] ({h.meta['source']} · {h.meta['loc']})\n{h.text}" for i, h in enumerate(hits, 1))


def build_messages(persona: str, context: str, history: list, question: str) -> list:
    if context:
        return RAG_PROMPT.format_messages(persona=persona, context=context, history=history, question=question)
    return CHAT_PROMPT.format_messages(persona=persona, history=history, question=question)
