"""Confirmed-scam memory scored locally. No API keys."""

import json
import logging
import os
import re
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

_STOP = {
    "this", "that", "with", "from", "your", "have", "will", "just",
    "they", "them", "about", "into", "http", "https", "www",
}


def _tokens(text: str) -> set:
    words = re.findall(r"[a-z0-9@]{4,}", (text or "").lower())
    return {word for word in words if word not in _STOP}


def _jaccard(left: set, right: set) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _cosine(left: List[float], right: List[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class ScamMemory:
    """Remembers confirmed scam texts and scores new messages against them."""

    def __init__(self, data_dir: str = "data", embedder=None, max_entries: int = 200):
        self.path = os.path.join(data_dir, "scam_memory.json")
        self.embedder = embedder
        self.max_entries = max_entries
        self.entries: List[dict] = []
        os.makedirs(data_dir, exist_ok=True)
        self._load()

    def add(self, text: str) -> bool:
        cleaned = (text or "").strip()
        if len(cleaned) < 12:
            return False
        if any(entry["text"] == cleaned for entry in self.entries):
            return False
        self.entries.append({"text": cleaned, "vector": self._embed(cleaned)})
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
        self._save()
        return True

    def absorb(self, texts: List[str]) -> int:
        added = 0
        for text in texts:
            if self.add(text):
                added += 1
        return added

    def score(self, text: str) -> Tuple[float, str]:
        """Return (similarity, kind). kind is embedding or overlap."""
        if not text or len(text.strip()) < 12 or not self.entries:
            return 0.0, "overlap"

        query_vector = self._embed(text)
        query_tokens = _tokens(text)
        best = 0.0
        kind = "overlap"
        for entry in self.entries:
            vector = entry.get("vector")
            if query_vector is not None and vector:
                similarity = _cosine(query_vector, vector)
                if similarity > best:
                    best = similarity
                    kind = "embedding"
            else:
                similarity = _jaccard(query_tokens, _tokens(entry["text"]))
                if similarity > best:
                    best = similarity
                    kind = "overlap"
        return best, kind

    def _embed(self, text: str) -> Optional[List[float]]:
        if not self.embedder:
            return None
        try:
            vector = self.embedder(text)
            if hasattr(vector, "tolist"):
                vector = vector.tolist()
            if vector and isinstance(vector[0], (list, tuple)):
                vector = list(vector[0])
            return [float(value) for value in vector]
        except Exception as exc:
            logger.debug(f"Scam embedding skipped: {exc}")
            return None

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except Exception as exc:
            logger.error(f"Could not load scam memory: {exc}")
            return

        entries = []
        for item in raw[-self.max_entries:]:
            if isinstance(item, str):
                text, vector = item, None
            elif isinstance(item, dict):
                text, vector = item.get("text", ""), item.get("vector")
            else:
                continue
            if not text:
                continue
            if vector is None:
                vector = self._embed(text)
            entries.append({"text": text, "vector": vector})
        self.entries = entries

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump(self.entries, handle, ensure_ascii=False)
        except Exception as exc:
            logger.error(f"Could not save scam memory: {exc}")
