"""MindDesk — chat assistant + document RAG workspace (PDF, Word, PowerPoint, Excel, CSV, text, JSON).
Run:  streamlit run app.py      (the OpenAI key is entered on the unlock screen and never written to disk)"""
import hashlib
import html
import time

import pandas as pd
import plotly.express as px
import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage
from openai import OpenAI

from src import chat_store
from src.config import (ACTIONS_DOCS, APP_ICON, APP_NAME, CHIPS_GENERAL, DEFAULT_MODEL, DEFAULT_THEME, EMBED_DB,
                        FILE_TYPES, MAX_FILE_MB, MODEL_OPTIONS, PERSIST, PERSONAS, TAGLINE, THEMES, env_api_key)
from src.llm import build_llm, token_stream, validate_key
from src.loaders import load_file
from src.rag import EmbeddingCache, add_document, build_messages, format_context, retrieve
from src.theme import css, plot_layout
from src.vectorstore import VectorStore

st.set_page_config(page_title=APP_NAME, page_icon=APP_ICON, layout="wide", initial_sidebar_state="expanded")
S = st.session_state
S.setdefault("theme", DEFAULT_THEME)
S.theme = S.theme
st.markdown(css(S.theme), unsafe_allow_html=True)

PAGES = ["💬 Chat", "📚 Knowledge", "📊 Data", "🛠 Studio"]
ICONS = {"pdf": "📕", "docx": "📘", "pptx": "📙", "xlsx": "📗", "xlsm": "📗", "csv": "🧾", "tsv": "🧾", "txt": "📄", "md": "📝", "json": "🧩"}
THINKING = '<div class="thinking"><span></span><span></span><span></span></div>'
SETTINGS = dict(model=DEFAULT_MODEL, temp=0.3, use_kb=True, chunk=1000, overlap=150, topk=5, mmr=True, thr=0.15,
                page=PAGES[0], wide=False, up_n=0, last={})


@st.cache_resource
def get_cache():
    return EmbeddingCache(EMBED_DB) if PERSIST else None


def reveal(text: str, step: float = 0.09, hl: str = "") -> str:
    """Words blur into focus one after another (the headline motion from the reference design)."""
    out = [f'<span class="rv" style="animation-delay:{0.1 + i * step:.2f}s">{html.escape(w)}</span>' for i, w in enumerate(text.split())]
    if hl:
        out.append(f'<span class="rv" style="animation-delay:{0.1 + len(out) * step:.2f}s"><span class="hl">{html.escape(hl)}</span></span>')
    return " ".join(out)


# ------------------------------------------------------------------ state
def init_state() -> None:
    for k, v in SETTINGS.items():
        S.setdefault(k, v)
        S[k] = S[k]  # keep widget-bound values alive while their widget is not on screen
    if "chats" not in S:
        S.chats, S.active, S.pending = chat_store.load(), None, False
        S.kb, S.docs, S.tables, S.hashes = VectorStore(), {}, {}, set()
    if S.get("active") not in S.chats:
        S.active = None
        new_chat()


def new_chat() -> None:
    cur = S.chats.get(S.get("active"))
    if cur is not None and not cur["messages"]:
        return
    cid = chat_store.new_id()
    S.chats[cid] = chat_store.new_chat()
    S.active = cid


def open_chat(cid: str) -> None:
    S.active, S.pending, S.page = cid, False, PAGES[0]


def delete_chat(cid: str) -> None:
    S.chats.pop(cid, None)
    chat_store.save(S.chats)
    if S.active == cid:
        S.active, S.pending = None, False
        new_chat()


def submit_prompt(text: str, wide: bool = False) -> None:
    chat = S.chats[S.active]
    chat["messages"].append({"role": "user", "content": text})
    if sum(m["role"] == "user" for m in chat["messages"]) == 1:
        chat["title"] = " ".join(text.split())[:40]
    chat["updated"] = time.time()
    chat_store.save(S.chats)
    S.pending, S.wide = True, wide


def submit_cb(text: str, wide: bool = False) -> None:
    """Button callback: switch to the chat page (allowed before widgets render), then submit."""
    S.page = PAGES[0]
    submit_prompt(text, wide)


def active_sources() -> set:
    return {n for n, d in S.docs.items() if d["enabled"]}


def set_persona(cid: str) -> None:
    chat, p = S.chats[cid], S[f"persona_{cid}"]
    chat["persona"] = p
    if p != "Custom":
        chat["system"] = S[f"system_{cid}"] = PERSONAS[p]
    chat_store.save(S.chats)


def system_edited(cid: str) -> None:
    chat = S.chats[cid]
    chat["system"] = S[f"system_{cid}"]
    if chat["system"] != PERSONAS.get(chat["persona"]):
        chat["persona"] = S[f"persona_{cid}"] = "Custom"
    chat_store.save(S.chats)


def remove_doc(name: str) -> None:
    d = S.docs.pop(name, None)
    S.kb.remove_source(name)
    for key in [k for k in S.tables if k.startswith(f"{name} › ")]:
        S.tables.pop(key)
    if d:
        S.hashes.discard(d["hash"])


# ------------------------------------------------------------------ indexing
def index_files(files) -> None:
    client = OpenAI(api_key=S.api_key, timeout=60)
    added = 0
    with st.status("Indexing your files…", expanded=True) as status:
        for f in files:
            data = f.getvalue()
            if len(data) > MAX_FILE_MB * 1024 * 1024:
                st.error(f"{f.name}: larger than {MAX_FILE_MB} MB — skipped.")
                continue
            h = hashlib.sha256(data).hexdigest()
            if h in S.hashes:
                st.write(f"↩︎ {f.name} is already indexed.")
                continue
            name, n = f.name, 2
            while name in S.docs:
                name, n = f"{f.name} ({n})", n + 1
            try:
                st.write(f"📖 Reading **{name}**")
                doc = load_file(name, data)
                st.write(f"🧮 Splitting and embedding {doc.units} {doc.unit_label}…")
                chunks = add_document(S.kb, client, doc, S.chunk, S.overlap, get_cache())
            except Exception as exc:  # noqa: BLE001
                st.error(f"{f.name}: {exc}")
                continue
            S.docs[name] = dict(kind=doc.kind, chunks=chunks, chars=doc.chars, units=doc.units, unit_label=doc.unit_label,
                                tables=len(doc.tables), enabled=True, hash=h, warnings=doc.warnings)
            for label, df in doc.tables.items():
                S.tables[f"{name} › {label}"] = df
            S.hashes.add(h)
            added += 1
            for w in doc.warnings:
                st.warning(w)
            st.write(f"✅ {name}: {chunks} chunks")
        status.update(label=f"Done — {added} file(s) added", state="complete", expanded=False)
    if added:
        S.up_n += 1
        st.rerun()


# ------------------------------------------------------------------ gate
def gate() -> None:
    _, col, _ = st.columns([1, 6, 1])
    with col:
        st.markdown('<div class="eyebrow">Welcome to ' + APP_NAME + '</div>'
                    f'<div class="display">{reveal("Ask your documents", hl="anything.")}</div>'
                    f'<div class="lead">{TAGLINE} Enter your OpenAI API key to open the workspace.</div>', unsafe_allow_html=True)
        with st.form("login"):
            name = st.text_input("Your name (optional)", placeholder="e.g. Alex")
            key = st.text_input("OpenAI API key", type="password", placeholder="sk-...")
            go = st.form_submit_button("Unlock workspace", type="primary", width="stretch")
        use_env = bool(env_api_key()) and st.button("Use key from .env", width="stretch")
        st.selectbox("Theme", list(THEMES), key="theme")
        st.caption("Your key stays in this browser session's memory only — it is never written to disk or logged.")
        st.markdown('<div class="chips">' + "".join(f'<span class="chip">{t}</span>' for t in
                    ("PDF", "Word", "Excel", "PowerPoint", "CSV", "Text", "JSON")) + "</div>", unsafe_allow_html=True)
        if go or use_env:
            k = env_api_key() if use_env else key.strip()
            if not k.startswith("sk-"):
                st.error("An OpenAI key starts with `sk-`. Please paste a valid key.")
                return
            with st.spinner("Verifying your key…"):
                err = validate_key(k)
            if err:
                st.error(err)
            else:
                S.authed, S.api_key, S.user_name = True, k, name.strip()
                st.rerun()


# ------------------------------------------------------------------ sidebar
def sidebar() -> None:
    chat, cid = S.chats[S.active], S.active
    with st.sidebar:
        st.markdown(f'<div class="brand">{APP_ICON} {APP_NAME}</div>', unsafe_allow_html=True)
        st.button("＋ New chat", key="new_chat", on_click=new_chat, type="primary", width="stretch")
        q = st.text_input("Search chats", key="search", placeholder="🔍 Search chats", label_visibility="collapsed").strip().lower()
        st.markdown('<div class="recents">Recents</div>', unsafe_allow_html=True)
        items = sorted(((i, c) for i, c in S.chats.items() if c["messages"] and q in c["title"].lower()),
                       key=lambda x: x[1]["updated"], reverse=True)
        with st.container(height=210, border=False):
            if not items:
                st.caption("No chats found." if q else "Your chats will appear here.")
            for i, c in items:
                a, b = st.columns([6, 1], gap="small", vertical_alignment="center")
                a.button(c["title"], key=f"{'active' if i == cid else 'chat'}_{i}", on_click=open_chat, args=(i,), width="stretch")
                b.button("✕", key=f"del_{i}", on_click=delete_chat, args=(i,), help="Delete chat")
        st.selectbox("🎨 Theme", list(THEMES), key="theme")
        with st.expander("Model & persona"):
            st.selectbox("Model", MODEL_OPTIONS, key="model", accept_new_options=True, help="Type any other model name too.")
            st.slider("Creativity", 0.0, 1.0, step=0.1, key="temp")
            S.setdefault(f"persona_{cid}", chat["persona"] if chat["persona"] in PERSONAS else "Custom")
            S.setdefault(f"system_{cid}", chat["system"])
            st.selectbox("Persona (this chat)", list(PERSONAS), key=f"persona_{cid}", on_change=set_persona, args=(cid,))
            st.text_area("System role", key=f"system_{cid}", height=110, on_change=system_edited, args=(cid,))
        with st.expander("Document search"):
            st.toggle("Use my documents in answers", key="use_kb")
            st.slider("Chunk size", 500, 2000, step=100, key="chunk", help="Applies to files indexed from now on.")
            st.slider("Chunk overlap", 0, 400, step=50, key="overlap")
            st.slider("Passages per answer (k)", 2, 10, key="topk")
            st.toggle("Diverse results (MMR)", key="mmr")
            st.slider("Relevance threshold", 0.0, 0.6, step=0.05, key="thr")
        st.download_button("⬇️ Download chat", chat_store.export_markdown(chat), f"{chat['title'][:30] or 'chat'}.md", width="stretch")
        st.button("Logout", key="logout", on_click=lambda: S.clear(), width="stretch")


# ------------------------------------------------------------------ chat page
def render_sources(srcs: list) -> None:
    st.markdown('<div class="chips">' + "".join(
        f'<span class="chip"><b>{i}</b>{html.escape(s["source"])} · {html.escape(s["loc"])}</span>' for i, s in enumerate(srcs, 1)) + "</div>",
        unsafe_allow_html=True)
    with st.expander("🔍 Retrieved passages"):
        for i, s in enumerate(srcs, 1):
            score = f" · relevance {s['score']:.2f}" if s.get("score") is not None else ""
            st.markdown(f"**[{i}] {s['source']} · {s['loc']}**{score}")
            st.text(s["text"])


def to_lc(m: dict):
    return HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"])


def answer_pending(chat: dict) -> None:
    msgs, q = chat["messages"], chat["messages"][-1]["content"]
    hits, error, reply = [], None, ""
    with st.chat_message("assistant"):
        slot = st.empty()
        slot.markdown(THINKING, unsafe_allow_html=True)
        try:
            allowed = active_sources()
            if S.use_kb and allowed and len(S.kb):
                prev = [m["content"] for m in msgs[:-1] if m["role"] == "user"]
                hits = retrieve(S.kb, OpenAI(api_key=S.api_key, timeout=60), q, prev[-1] if prev else "", k=S.topk, mmr=S.mmr,
                                threshold=S.thr, allowed=allowed, wide=S.wide, cache=get_cache())
            messages = build_messages(chat["system"], format_context(hits), [to_lc(m) for m in msgs[:-1][-20:]], q)
            reply = st.write_stream(token_stream(build_llm(S.api_key, S.model, S.temp), messages, slot.empty))
        except Exception as exc:  # noqa: BLE001
            slot.empty()
            error = f"The request failed: {exc}"
        srcs = [dict(source=h.meta["source"], loc=h.meta["loc"], score=h.score, text=h.text[:600]) for h in hits]
        if not error and srcs:
            render_sources(srcs)
    S.pending, S.wide = False, False
    if error:
        msgs.pop()
        if not msgs:
            chat["title"] = "New chat"
        chat_store.save(S.chats)
        S.last_error = error
        st.rerun()
    S.last = dict(query=q, hits=srcs)
    msgs.append({"role": "assistant", "content": reply, "sources": srcs})
    chat["updated"] = time.time()
    chat_store.save(S.chats)


def page_chat() -> None:
    chat, msgs = S.chats[S.active], S.chats[S.active]["messages"]
    if err := S.pop("last_error", None):
        st.error(err)
    n_active = len(active_sources())
    if n_active and S.use_kb:
        st.markdown(f'<div class="chips"><span class="chip"><b>{n_active}</b>document(s) active in this chat</span></div>', unsafe_allow_html=True)
    if not msgs:
        greeting = f"Hello, {S.user_name}" if S.get("user_name") else "How can I help today?"
        st.markdown(f'<div style="height:7vh"></div><div class="greeting">{reveal(greeting)}</div>', unsafe_allow_html=True)
        with st.container(key="hero_input"):
            prompt = st.chat_input("Ask anything — or ask about your documents", key="chat_prompt")
        st.write("")
        if n_active and S.use_kb:
            cols = st.columns(2)
            for i, (label, text, wide) in enumerate(ACTIONS_DOCS):
                cols[i % 2].button(label, key=f"act_{i}", on_click=submit_cb, args=(text, wide), width="stretch", help=text)
        else:
            cols = st.columns(2)
            for i, (label, text) in enumerate(CHIPS_GENERAL):
                cols[i % 2].button(label, key=f"chip_{i}", on_click=submit_cb, args=(text,), width="stretch", help=text)
            st.caption("Tip: open **📚 Knowledge** to add PDF, Word, Excel, PowerPoint or CSV files and chat with them.")
    else:
        for m in msgs:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
                if m.get("sources"):
                    render_sources(m["sources"])
        if n_active and S.use_kb and not S.pending:
            cols = st.columns(len(ACTIONS_DOCS))
            for i, (label, text, wide) in enumerate(ACTIONS_DOCS):
                cols[i].button(label, key=f"act_{i}", on_click=submit_cb, args=(text, wide), width="stretch", help=text)
        prompt = st.chat_input("Ask anything — or ask about your documents", key="chat_prompt")
    if prompt and prompt.strip():
        submit_prompt(prompt.strip())
        st.rerun()
    if S.pending and msgs and msgs[-1]["role"] == "user":
        answer_pending(chat)


# ------------------------------------------------------------------ knowledge page
def page_knowledge() -> None:
    st.markdown('<div class="eyebrow">Knowledge</div><div class="display" style="font-size:2.4rem">Add your <span class="hl">documents</span></div>', unsafe_allow_html=True)
    st.caption("PDF · Word · PowerPoint · Excel (.xlsx) · CSV/TSV · TXT/Markdown · JSON — up to 25 MB each. Spreadsheets also appear in the Data tab.")
    files = st.file_uploader("Drop files here", type=FILE_TYPES, accept_multiple_files=True, key=f"uploader_{S.up_n}", label_visibility="collapsed")
    if files and st.button(f"Index {len(files)} file(s)", type="primary"):
        index_files(files)
    if not S.docs:
        st.info("No documents yet. Upload files above, then ask about them in **💬 Chat**.")
        return
    st.markdown(f'<div class="stats"><div class="stat"><small>Files</small><b>{len(S.docs)}</b></div>'
                f'<div class="stat"><small>Chunks</small><b>{len(S.kb):,}</b></div>'
                f'<div class="stat"><small>Tables</small><b>{len(S.tables)}</b></div>'
                f'<div class="stat"><small>Active</small><b>{len(active_sources())}</b></div></div>', unsafe_allow_html=True)
    for name, d in list(S.docs.items()):
        a, b, c = st.columns([7, 2, 1], vertical_alignment="center")
        a.markdown(f'<div class="doc"><div class="ico">{ICONS.get(d["kind"], "📄")}</div><div><b>{html.escape(name)}</b><br>'
                   f'<span>{d["units"]} {d["unit_label"]} · {d["chunks"]} chunks · {d["chars"]:,} characters</span></div></div>', unsafe_allow_html=True)
        d["enabled"] = b.checkbox("Active", value=d["enabled"], key=f"en_{d['hash'][:10]}")
        c.button("🗑", key=f"rm_{d['hash'][:10]}", on_click=remove_doc, args=(name,), help="Remove file")
        for w in d["warnings"]:
            st.caption(f"⚠️ {w}")


# ------------------------------------------------------------------ data page
def table_html(df: pd.DataFrame, rows: int = 50) -> str:
    return '<div class="tblwrap">' + df.head(rows).to_html(classes="tbl", border=0, escape=True, index=False) + "</div>"


def ask_about_table(label: str) -> None:
    submit_cb(f"Analyse the table '{label}': give the 5 most important insights, any anomalies or data-quality issues, "
                  "and suggested next analyses. Cite figures.")


def page_data() -> None:
    st.markdown('<div class="eyebrow">Data explorer</div><div class="display" style="font-size:2.4rem">See your <span class="hl">tables</span></div>', unsafe_allow_html=True)
    if not S.tables:
        st.info("Upload an Excel, CSV, JSON (list of records) or a Word file with tables in **📚 Knowledge** to explore it here.")
        return
    label = st.selectbox("Table", list(S.tables))
    df = S.tables[label]
    num, cols = list(df.select_dtypes("number").columns), list(df.columns)
    miss = df.isna().mean().mean() * 100
    st.markdown(f'<div class="stats"><div class="stat"><small>Rows</small><b>{len(df):,}</b></div><div class="stat"><small>Columns</small><b>{len(cols)}</b></div>'
                f'<div class="stat"><small>Numeric</small><b>{len(num)}</b></div><div class="stat"><small>Missing</small><b>{miss:.1f}%</b></div></div>', unsafe_allow_html=True)
    st.markdown(table_html(df), unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇️ Download CSV", df.to_csv(index=False), f"{label.split('›')[-1].strip()}.csv", width="stretch")
    c2.button("🤖 Ask AI to analyse", on_click=ask_about_table, args=(label,), type="primary", width="stretch")
    if num:
        with st.expander("Column statistics"):
            st.markdown(table_html(df[num].describe().T.round(2).reset_index().rename(columns={"index": "column"})), unsafe_allow_html=True)
    st.markdown("#### Chart builder")
    k1, k2, k3, k4 = st.columns(4)
    kind = k1.selectbox("Chart", ["Bar", "Line", "Scatter", "Histogram", "Pie", "Box"])
    x = k2.selectbox("X / category", cols)
    y = k3.selectbox("Y (numeric)", num) if num and kind != "Histogram" else None
    agg = k4.selectbox("Aggregate", ["sum", "mean", "count", "max", "min"]) if kind in ("Bar", "Line", "Pie") else None
    try:
        lay = plot_layout(S.theme)
        if kind in ("Bar", "Line", "Pie") and y:
            g = df.groupby(x, dropna=True)[y].agg(agg).reset_index()
            g = g.sort_values(x if kind == "Line" else y, ascending=kind == "Line").tail(25) if kind == "Line" else g.sort_values(y, ascending=False).head(25)
            fig = {"Bar": px.bar, "Line": px.line, "Pie": px.pie}[kind](g, **({"names": x, "values": y} if kind == "Pie" else {"x": x, "y": y}))
        elif kind == "Scatter" and y:
            fig = px.scatter(df, x=x, y=y)
        elif kind == "Box" and y:
            fig = px.box(df, x=x if df[x].nunique() <= 25 else None, y=y)
        elif kind == "Histogram":
            fig = px.histogram(df, x=x)
        else:
            st.info("This chart needs a numeric column.")
            return
        fig.update_layout(**lay)
        st.plotly_chart(fig, width="stretch")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Could not draw that chart ({type(exc).__name__}). Try another column combination.")


# ------------------------------------------------------------------ studio page
def page_studio() -> None:
    st.markdown('<div class="eyebrow">Studio</div><div class="display" style="font-size:2.4rem">Under the <span class="hl">hood</span></div>', unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["Retrieval inspector", "Prompt preview", "Index & storage"])
    with t1:
        last = S.last
        if not last:
            st.info("Ask a question about your documents to see which passages were retrieved.")
        else:
            st.markdown(f"**Question:** {html.escape(last['query'])}")
            if last["hits"]:
                st.markdown(table_html(pd.DataFrame([dict(rank=i, source=h["source"], location=h["loc"],
                            score=None if h["score"] is None else round(h["score"], 3), preview=h["text"][:120]) for i, h in enumerate(last["hits"], 1)])), unsafe_allow_html=True)
            else:
                st.caption("No passages were used for the last answer (plain chat).")
    with t2:
        chat = S.chats[S.active]
        st.code(chat["system"], language="text")
        st.caption("When documents are active, the numbered context and the citation rules are appended to this system prompt.")
    with t3:
        cache = get_cache()
        st.markdown(f'<div class="stats"><div class="stat"><small>Chunks</small><b>{len(S.kb):,}</b></div>'
                    f'<div class="stat"><small>Cached embeddings</small><b>{cache.count() if cache else 0:,}</b></div>'
                    f'<div class="stat"><small>Saved on device</small><b>{"Yes" if PERSIST else "No"}</b></div></div>', unsafe_allow_html=True)
        st.caption("Chats are saved to data/chats.json and embeddings to data/embed_cache.sqlite when MINDDESK_PERSIST=1. "
                   "Set it to 0 on shared or cloud deployments.")
        if S.docs:
            rows = [dict(file=n, **{k: v for k, v in d.items() if k in ("kind", "units", "chunks", "chars", "enabled")}) for n, d in S.docs.items()]
            st.markdown(table_html(pd.DataFrame(rows)), unsafe_allow_html=True)


# ------------------------------------------------------------------ main
if not S.get("authed"):
    gate()
else:
    init_state()
    sidebar()
    st.radio("Navigate", PAGES, key="page", horizontal=True, label_visibility="collapsed")
    {PAGES[0]: page_chat, PAGES[1]: page_knowledge, PAGES[2]: page_data, PAGES[3]: page_studio}[S.page]()
