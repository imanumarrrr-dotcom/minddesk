"""A tiny in-memory vector store (pure NumPy): cosine search, MMR re-ranking, per-file filtering."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np


@dataclass
class Hit:
    text: str
    meta: dict
    score: float | None = None


class VectorStore:
    def __init__(self) -> None:
        self.texts: list[str] = []
        self.metas: list[dict] = []
        self._m: np.ndarray | None = None

    def __len__(self) -> int:
        return len(self.texts)

    def add(self, texts, metas, vecs) -> None:
        v = np.asarray(vecs, dtype=np.float32)
        v = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)
        self._m = v if self._m is None else np.vstack([self._m, v])
        self.texts += list(texts)
        self.metas += list(metas)

    def remove_source(self, name: str) -> None:
        keep = [i for i, m in enumerate(self.metas) if m["source"] != name]
        self.texts = [self.texts[i] for i in keep]
        self.metas = [self.metas[i] for i in keep]
        self._m = self._m[keep] if (self._m is not None and keep) else None

    def sources(self) -> dict:
        return dict(Counter(m["source"] for m in self.metas))

    def _idx(self, allowed) -> list[int]:
        return [i for i, m in enumerate(self.metas) if allowed is None or m["source"] in allowed]

    def search(self, qvec, k: int = 4, mmr: bool = True, threshold: float = 0.0, allowed=None,
               fetch_k: int | None = None, lam: float = 0.65) -> list[Hit]:
        idx = self._idx(allowed)
        if not idx or self._m is None:
            return []
        q = np.asarray(qvec, dtype=np.float32)
        q = q / (np.linalg.norm(q) + 1e-12)
        sims = self._m[idx] @ q
        order = np.argsort(-sims)[: fetch_k or k * 4]
        cand = [(idx[j], float(sims[j])) for j in order if sims[j] >= threshold]
        if not cand:
            return []
        if not mmr or len(cand) <= k:
            sel = cand[:k]
        else:  # maximal marginal relevance: relevant AND diverse
            sel, rest = [cand[0]], cand[1:]
            while rest and len(sel) < k:
                best = max(rest, key=lambda c: lam * c[1] - (1 - lam) * max(float(self._m[c[0]] @ self._m[j]) for j, _ in sel))
                sel.append(best)
                rest.remove(best)
        return [Hit(self.texts[i], self.metas[i], s) for i, s in sel]

    def profiles(self, allowed=None) -> list[Hit]:
        """Table summaries / small full tables (role == 'summary')."""
        return [Hit(self.texts[i], self.metas[i]) for i in self._idx(allowed) if self.metas[i].get("role") == "summary"]

    def sample(self, n: int = 14, allowed=None) -> list[Hit]:
        """Evenly spaced chunks across all active files — used for 'summarize everything' requests."""
        idx = self._idx(allowed)
        if not idx:
            return []
        chosen = sorted({idx[int(j)] for j in np.linspace(0, len(idx) - 1, min(n, len(idx)))})
        return [Hit(self.texts[i], self.metas[i]) for i in chosen]
