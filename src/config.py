"""Central settings: names, models, personas, file types and the three colour themes."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

APP_NAME = "MindDesk"
APP_ICON = "🪷"
TAGLINE = "Your assistant and your documents, in one calm workspace."

DEFAULT_MODEL = "gpt-4o-mini"
MODEL_OPTIONS = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "gpt-5.2"]  # any other name can be typed in
EMBED_MODEL = "text-embedding-3-small"

DATA_DIR = Path("data")
CHATS_FILE = DATA_DIR / "chats.json"
EMBED_DB = DATA_DIR / "embed_cache.sqlite"
PERSIST = os.getenv("MINDDESK_PERSIST", "1") != "0"

FILE_TYPES = ["pdf", "docx", "pptx", "xlsx", "xlsm", "csv", "tsv", "txt", "md", "json"]
MAX_FILE_MB = 25

DEFAULT_SYSTEM = "You are a helpful, accurate and concise assistant."
PERSONAS = {
    "Helpful assistant": DEFAULT_SYSTEM,
    "Data analyst": "You are a careful data analyst. Reason step by step, state assumptions, never invent numbers, "
                    "and show how any figure was derived from the data you were given.",
    "Research assistant": "You are a meticulous research assistant. Compare sources, point out contradictions and "
                          "uncertainty, and keep claims tied to evidence.",
    "Study tutor": "You are a patient tutor. Explain simply first, then add depth, and check understanding with a short question.",
    "Business writer": "You are a professional business writer. Produce clear, polished, well-structured text for executives.",
    "Custom": "",
}

CHIPS_GENERAL = [
    ("✍️ Write a polite email", "Write a polite email asking my manager for a deadline extension."),
    ("💡 Explain simply", "Explain how neural networks work in simple terms with an everyday analogy."),
    ("📊 Plan a dashboard", "Suggest the key metrics and layout for a monthly sales dashboard."),
    ("🧭 Study plan", "Give me a practical 3-day study plan to start learning Python."),
]
ACTIONS_DOCS = [
    ("📝 Summarize", "Summarize the active documents in a few clear paragraphs, noting what each file contributes.", True),
    ("🔑 Key points", "List the key points of the active documents as bullet points with citations.", True),
    ("📈 Insights", "What are the most important insights, trends or anomalies in the active documents? Cite figures.", True),
    ("❓ Suggest questions", "Suggest 6 good questions I could ask about these documents.", True),
]

# ------------------------------------------------------------------ themes
# palette from the design reference: Ice Silver #DDE3E8 · Deep Aubergine #3A0F34 · Marigold #EAAA00
THEMES = {
    "Ice Silver": dict(scheme="light", bg1="#EEF1F4", bg2="#DDE3E8", bg3="#CDD5DC", surface="rgba(255,255,255,0.60)",
                       field="#F8FAFB", text="#3A0F34", muted="#6A4764", accent="#EAAA00", accent2="#3A0F34",
                       onacc="#3A0F34", border="rgba(58,15,52,0.18)"),
    "Deep Aubergine": dict(scheme="dark", bg1="#3A0F34", bg2="#2B0A27", bg3="#1C0619", surface="rgba(221,227,232,0.07)",
                           field="#2F0C2B", text="#DDE3E8", muted="#B7A5B3", accent="#EAAA00", accent2="#F3C641",
                           onacc="#2A0A26", border="rgba(221,227,232,0.16)"),
    "Marigold": dict(scheme="light", bg1="#FFF1C2", bg2="#F6D56B", bg3="#EAAA00", surface="rgba(255,255,255,0.50)",
                     field="#FFF9E3", text="#3A0F34", muted="#5E2B57", accent="#3A0F34", accent2="#6B2A62",
                     onacc="#FFF1C2", border="rgba(58,15,52,0.22)"),
}
DEFAULT_THEME = "Ice Silver"


def env_api_key() -> str:
    """Key from the environment — only offered in the UI when MINDDESK_ALLOW_ENV_KEY=1 (local use)."""
    if os.getenv("MINDDESK_ALLOW_ENV_KEY", "0") != "1":
        return ""
    return os.getenv("OPENAI_API_KEY", "").strip()
