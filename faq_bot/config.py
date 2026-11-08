import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    token: str
    faq_path: Path
    threshold: float
    admin_ids: frozenset
    unmatched_log: Path
    fallback_text: str

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.environ.get("BOT_TOKEN", "").strip()
        if not token:
            raise SystemExit("BOT_TOKEN is not set. See README.md")
        admins = frozenset(
            int(x) for x in os.environ.get("ADMIN_IDS", "").replace(";", ",").split(",") if x.strip().isdigit()
        )
        return cls(
            token=token,
            faq_path=Path(os.environ.get("FAQ_PATH", "data/faq.json")),
            threshold=float(os.environ.get("MATCH_THRESHOLD", "72")),
            admin_ids=admins,
            unmatched_log=Path(os.environ.get("UNMATCHED_LOG", "data/unmatched.log")),
            fallback_text=os.environ.get(
                "FALLBACK_TEXT",
                "Sorry, I couldn't find an answer to that. Could you rephrase the question? "
                "I've noted it so the team can add it to the FAQ.",
            ),
        )
