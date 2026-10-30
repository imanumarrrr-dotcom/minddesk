"""Chat history: create, title, save/load (JSON on this device) and export."""
import json
import os
import time
import uuid

from .config import CHATS_FILE, DEFAULT_SYSTEM, PERSIST


def new_chat() -> dict:
    return {"title": "New chat", "system": DEFAULT_SYSTEM, "persona": "Helpful assistant", "messages": [], "updated": time.time()}


def new_id() -> str:
    return uuid.uuid4().hex


def load() -> dict:
    if not PERSIST:
        return {}
    try:
        data = json.loads(CHATS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    chats = {}
    for cid, c in (data.items() if isinstance(data, dict) else []):
        if isinstance(c, dict) and isinstance(c.get("messages"), list):
            chats[cid] = {"title": c.get("title") or "New chat", "system": c.get("system") or DEFAULT_SYSTEM,
                          "persona": c.get("persona") or "Custom",
                          "messages": [m for m in c["messages"] if isinstance(m, dict) and "role" in m and "content" in m],
                          "updated": float(c.get("updated") or 0)}
    return chats


def save(chats: dict) -> None:
    if not PERSIST:
        return
    data = {cid: c for cid, c in chats.items() if c["messages"]}
    try:
        CHATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CHATS_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, CHATS_FILE)
    except OSError:
        pass  # read-only deployments: keep working in memory


def export_markdown(chat: dict) -> str:
    out = [f"# {chat['title']}", ""]
    for m in chat["messages"]:
        out += [f"**{'You' if m['role'] == 'user' else 'Assistant'}:**", "", m["content"], ""]
        for i, s in enumerate(m.get("sources") or [], 1):
            out.append(f"> [{i}] {s['source']} · {s['loc']}")
        out.append("")
    return "\n".join(out)
