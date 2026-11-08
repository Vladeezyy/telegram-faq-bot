"""Render a Telegram-style chat mock-up from REAL matcher output (for README / portfolio).

    python render_demo.py out.png
"""
import sys
import textwrap
from PIL import Image, ImageDraw, ImageFont

from faq_bot.matcher import FAQMatcher

FALLBACK = ("Sorry, I couldn't find an answer to that. Could you rephrase the question? "
            "I've noted it so the team can add it to the FAQ.")

QUESTIONS = [
    "hi! wht are ur working hourz?",
    "which payment methods do you have??",
    "product return, is it possible",
    "where is my parcel",
    "what's the bitcoin price today?",
]

W = 900
BG = (14, 22, 33)
IN = (33, 46, 61)
OUT = (46, 112, 180)
TXT = (235, 240, 245)
SUB = (150, 165, 180)
FONT = "/System/Library/Fonts/Helvetica.ttc"


def font(size, bold=False):
    try:
        return ImageFont.truetype(FONT, size, index=1 if bold else 0)
    except Exception:
        return ImageFont.load_default()


def bubble(draw, y, text, right, f, time_txt):
    maxw = int(W * 0.68)
    lines = []
    for para in text.split("\n"):
        lines += textwrap.wrap(para, width=46) or [""]
    lh = f.size + 7
    tw = max(draw.textlength(l, font=f) for l in lines)
    bw, bh = int(tw) + 36, lh * len(lines) + 34
    x = W - 24 - bw if right else 24
    color = OUT if right else IN
    draw.rounded_rectangle((x, y, x + bw, y + bh), radius=18, fill=color)
    ty = y + 14
    for l in lines:
        draw.text((x + 18, ty), l, font=f, fill=TXT)
        ty += lh
    draw.text((x + bw - 50, y + bh - 20), time_txt, font=font(12), fill=SUB)
    return y + bh + 12


def main(out="demo_chat.png"):
    m = FAQMatcher.from_file("data/faq.example.json")
    f = font(20)
    msgs = []
    t = 14 * 60 + 2
    for q in QUESTIONS:
        r = m.best(q)
        msgs.append((q, True, t)); t += 1
        msgs.append((r.entry.answer if r else FALLBACK, False, t)); t += 1
    # measure
    tmp = ImageDraw.Draw(Image.new("RGB", (W, 10)))
    y = 90
    for text, right, _ in msgs:
        y = bubble(tmp, y, text, right, f, "")
    H = y + 70
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # header
    d.rectangle((0, 0, W, 72), fill=(23, 33, 43))
    d.ellipse((20, 14, 64, 58), fill=(90, 160, 230))
    d.text((34, 24), "F", font=font(22, True), fill=TXT)
    d.text((80, 16), "Shop FAQ Bot", font=font(21, True), fill=TXT)
    d.text((80, 44), "bot", font=font(14), fill=SUB)
    y = 90
    for text, right, tm in msgs:
        y = bubble(d, y, text, right, f, f"{tm // 60:02d}:{tm % 60:02d}")
    # input bar
    d.rectangle((0, H - 58, W, H), fill=(23, 33, 43))
    d.rounded_rectangle((16, H - 48, W - 70, H - 10), radius=19, fill=(33, 46, 61))
    d.text((34, H - 40), "Message", font=font(17), fill=SUB)
    d.ellipse((W - 58, H - 50, W - 16, H - 8), fill=OUT)
    d.text((W - 28, H - 72), "", font=f, fill=TXT)
    img.save(out)
    print("saved", out, img.size)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "demo_chat.png")
