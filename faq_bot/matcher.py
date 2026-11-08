"""Fuzzy matching of user questions against a fixed Q&A knowledge base.

Design rules:
- The bot never invents answers. It returns an entry from the list or nothing.
- Matching is tolerant to typos, word order and extra words, but a result
  below ``threshold`` is treated as "no match".
- Knowledge base formats: JSON (list of {question, answer, aliases?}) or CSV
  with ``question,answer`` columns (optional ``aliases`` column, ``|``-separated).
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

def _word_anchor(a: str, b: str, sim) -> bool:
    """True when at least one word of ``a`` closely matches a word of ``b``.

    Prevents substring coincidences ("pay" inside "price") from scoring high.
    """
    wa, wb = a.split(), b.split()
    for x in wa:
        for y in wb:
            if len(x) >= 3 and len(y) >= 3 and sim(x, y) >= 80:
                return True
            if x == y:
                return True
    return False


try:  # fast path
    from rapidfuzz import fuzz  # type: ignore

    def _ratio(a: str, b: str) -> float:
        score = fuzz.token_set_ratio(a, b)
        if min(len(a), len(b)) >= 12:  # partial only makes sense for longer strings
            score = max(score, fuzz.partial_ratio(a, b) * 0.9)
        if not _word_anchor(a, b, fuzz.ratio):
            score = min(score, 50.0)
        return score

except ImportError:  # pure-stdlib fallback
    from difflib import SequenceMatcher

    def _sim(x: str, y: str) -> float:
        return 100.0 * SequenceMatcher(None, x, y).ratio()

    def _ratio(a: str, b: str) -> float:
        sa, sb = set(a.split()), set(b.split())
        token = _sim(" ".join(sorted(sa)), " ".join(sorted(sb)))
        overlap = 100.0 * len(sa & sb) / max(1, min(len(sa), len(sb)))
        fuzzy_hits = sum(1 for wa in sa if any(_sim(wa, wb) >= 72 for wb in sb))
        fuzzy = 100.0 * fuzzy_hits / max(1, min(len(sa), len(sb)))
        score = max(token, overlap * 0.9, fuzzy * 0.85)
        if not _word_anchor(a, b, _sim):
            score = min(score, 50.0)
        return score


_WORD_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_STOP = {
    "the", "a", "an", "is", "are", "do", "does", "can", "i", "you", "to", "of",
    "my", "me", "please", "how", "what", "where", "when", "it", "in", "on",
    "your", "ur", "u", "hey", "hi", "hello", "guys", "which", "have", "there",
    "и", "в", "на", "как", "что", "ли", "я", "вы", "мне", "по", "у", "а",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = _WORD_RE.sub(" ", text)
    words = [w for w in text.split() if w not in _STOP]
    return " ".join(words) or text.strip()


@dataclass
class Entry:
    question: str
    answer: str
    aliases: List[str] = field(default_factory=list)

    @property
    def variants(self) -> List[str]:
        return [self.question, *self.aliases]


@dataclass
class Match:
    entry: Entry
    score: float
    matched_text: str


class FAQMatcher:
    def __init__(self, entries: Iterable[Entry], threshold: float = 72.0):
        self.entries: List[Entry] = list(entries)
        self.threshold = threshold
        self._index = [
            (normalize(v), e) for e in self.entries for v in e.variants if v.strip()
        ]

    # ---------- loading ----------
    @classmethod
    def from_file(cls, path: str | Path, threshold: float = 72.0) -> "FAQMatcher":
        path = Path(path)
        if path.suffix.lower() == ".json":
            entries = cls._load_json(path)
        elif path.suffix.lower() in {".csv", ".tsv"}:
            entries = cls._load_csv(path)
        else:
            raise ValueError(f"Unsupported knowledge base format: {path.suffix}")
        return cls(entries, threshold)

    @staticmethod
    def _load_json(path: Path) -> List[Entry]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):  # {"question": "answer", ...}
            raw = [{"question": q, "answer": a} for q, a in raw.items()]
        out = []
        for item in raw:
            aliases = item.get("aliases") or []
            if isinstance(aliases, str):
                aliases = [a.strip() for a in aliases.split("|") if a.strip()]
            out.append(Entry(str(item["question"]), str(item["answer"]), list(aliases)))
        return out

    @staticmethod
    def _load_csv(path: Path) -> List[Entry]:
        out = []
        with path.open(encoding="utf-8-sig", newline="") as fh:
            sample = fh.read(2048)
            fh.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t") if sample else csv.excel
            reader = csv.DictReader(fh, dialect=dialect)
            cols = {c.lower().strip(): c for c in reader.fieldnames or []}
            qcol, acol = cols.get("question"), cols.get("answer")
            if not qcol or not acol:
                raise ValueError("CSV must have 'question' and 'answer' columns")
            alcol = cols.get("aliases")
            for row in reader:
                if not (row.get(qcol) or "").strip():
                    continue
                aliases = [a.strip() for a in (row.get(alcol) or "").split("|") if a.strip()] if alcol else []
                out.append(Entry(row[qcol].strip(), (row.get(acol) or "").strip(), aliases))
        return out

    # ---------- matching ----------
    def best(self, query: str) -> Optional[Match]:
        q = normalize(query)
        if not q:
            return None
        best: Optional[Match] = None
        for text, entry in self._index:
            if text == q:
                return Match(entry, 100.0, text)
            score = _ratio(q, text)
            if best is None or score > best.score:
                best = Match(entry, score, text)
        if best and best.score >= self.threshold:
            return best
        return None

    def top(self, query: str, n: int = 3) -> Sequence[Match]:
        q = normalize(query)
        scored = [Match(e, _ratio(q, t), t) for t, e in self._index]
        scored.sort(key=lambda m: m.score, reverse=True)
        seen, out = set(), []
        for m in scored:
            if id(m.entry) in seen:
                continue
            seen.add(id(m.entry))
            out.append(m)
            if len(out) >= n:
                break
        return out

    def __len__(self) -> int:
        return len(self.entries)
