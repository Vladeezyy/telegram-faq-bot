"""Offline chat with the FAQ engine, no Telegram token needed.

    python demo_cli.py data/faq.json
"""
import sys
from faq_bot.matcher import FAQMatcher

path = sys.argv[1] if len(sys.argv) > 1 else "data/faq.json"
m = FAQMatcher.from_file(path)
print(f"Loaded {len(m)} entries from {path}. Type a question, empty line to quit.\n")
while True:
    try:
        q = input("you> ").strip()
    except EOFError:
        break
    if not q:
        break
    r = m.best(q)
    if r:
        print(f"bot> {r.entry.answer}   [match {r.score:.0f}%: {r.entry.question}]\n")
    else:
        print("bot> Sorry, I couldn't find an answer to that. Could you rephrase?\n")
