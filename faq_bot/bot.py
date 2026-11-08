"""Telegram entry point. Run: python -m faq_bot.bot"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import Settings
from .matcher import FAQMatcher

log = logging.getLogger("faq_bot")


class FAQBot:
    def __init__(self, settings: Settings):
        self.s = settings
        self.matcher = FAQMatcher.from_file(settings.faq_path, settings.threshold)
        self.stats = {"questions": 0, "answered": 0, "unmatched": 0}
        self.s.unmatched_log.parent.mkdir(parents=True, exist_ok=True)

    # ----- helpers -----
    def _is_admin(self, update: Update) -> bool:
        return bool(update.effective_user and update.effective_user.id in self.s.admin_ids)

    def _log_unmatched(self, update: Update, text: str) -> None:
        user = update.effective_user
        line = (
            f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}\t"
            f"{user.id if user else '-'}\t{user.username if user else '-'}\t{text!r}\n"
        )
        with self.s.unmatched_log.open("a", encoding="utf-8") as fh:
            fh.write(line)

    # ----- handlers -----
    async def start(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Hi! Ask me a question and I'll answer from our FAQ.\n"
            f"I currently know {len(self.matcher)} topics."
        )

    async def help(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        text = "Just type your question in plain words.\n\nCommands:\n/start – intro\n/help – this message"
        if self._is_admin(update):
            text += "\n\nAdmin:\n/reload – reload the Q&A file\n/stats – usage counters\n/test <question> – show top matches with scores"
        await update.message.reply_text(text)

    async def reload(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_admin(update):
            return
        try:
            self.matcher = FAQMatcher.from_file(self.s.faq_path, self.s.threshold)
            await update.message.reply_text(f"Reloaded: {len(self.matcher)} entries.")
        except Exception as exc:  # noqa: BLE001
            await update.message.reply_text(f"Reload failed: {exc}")

    async def stats(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_admin(update):
            return
        s = self.stats
        await update.message.reply_text(
            f"Questions: {s['questions']}\nAnswered: {s['answered']}\nUnmatched: {s['unmatched']}\n"
            f"Entries: {len(self.matcher)}  Threshold: {self.s.threshold}"
        )

    async def test(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_admin(update):
            return
        q = " ".join(ctx.args or [])
        if not q:
            await update.message.reply_text("Usage: /test your question here")
            return
        lines = [f"{m.score:5.1f}  {m.entry.question}" for m in self.matcher.top(q)]
        await update.message.reply_text("Top matches:\n" + "\n".join(lines))

    async def answer(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.message
        if not msg or not msg.text:
            return
        text = msg.text.strip()
        # In groups, only react when mentioned or replied to, so the bot does not spam.
        if msg.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            me = ctx.bot.username
            mentioned = me and f"@{me}".lower() in text.lower()
            replied = msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.id == ctx.bot.id
            if not (mentioned or replied):
                return
            if me:
                text = text.replace(f"@{me}", "").strip()
        self.stats["questions"] += 1
        match = self.matcher.best(text)
        if match:
            self.stats["answered"] += 1
            await msg.reply_text(match.entry.answer, disable_web_page_preview=True)
        else:
            self.stats["unmatched"] += 1
            self._log_unmatched(update, text)
            await msg.reply_text(self.s.fallback_text)


def build_app(settings: Settings) -> Application:
    bot = FAQBot(settings)
    app = Application.builder().token(settings.token).build()
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("help", bot.help))
    app.add_handler(CommandHandler("reload", bot.reload))
    app.add_handler(CommandHandler("stats", bot.stats))
    app.add_handler(CommandHandler("test", bot.test))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.answer))
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    app = build_app(settings)
    log.info("FAQ bot started with %s entries", len(FAQMatcher.from_file(settings.faq_path)))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
