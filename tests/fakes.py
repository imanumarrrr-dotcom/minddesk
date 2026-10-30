"""Offline stand-ins for OpenAI so everything can be tested without a key."""
import hashlib
import re
from types import SimpleNamespace

import numpy as np

DIM = 128


def fake_vec(text: str) -> list:
    v = np.zeros(DIM, dtype=np.float32)
    for w in re.findall(r"\w+", text.lower()):
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1
    return v.tolist()


class FakeClient:
    def __init__(self, *a, **k):
        self.calls = 0
        self.embeddings = SimpleNamespace(create=self._create)

    def _create(self, model, input):
        self.calls += 1
        return SimpleNamespace(data=[SimpleNamespace(embedding=fake_vec(t)) for t in input])


class FakeLLM:
    def stream(self, messages):
        text = "Fake answer using [1]."
        for w in text.split(" "):
            yield SimpleNamespace(content=w + " ")
