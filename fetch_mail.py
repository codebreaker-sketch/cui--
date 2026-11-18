"""Optional: turn event-planning emails into messages.   python fetch_mail.py

Reads UNREAD emails from the Gmail inbox over IMAP (same SMTP_USER / SMTP_PASS app password as the login),
keeps only event-planning ones, and writes each as a .txt file into inbox/. Then run `python main.py`
as usual: the same pipeline reads, validates, accepts or rejects them. Nothing else is changed.
"""
import email
import imaplib
import os
import re
import time
from email.header import decode_header
from email.utils import parsedate_to_datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from planner import llm  # noqa: E402,F401  (loads .env)

WORDS = re.compile(r"(?i)hackathon|event|budget|venue|hall|cater|lunch|food|judge|honorar|students?|teams?|seats?|"
                   r"schedule|prayer|break|prize|printing|\bRs\.?\s*\d|pkr|per head|fi kas|khana|bajat")


def _text(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
                return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
                return re.sub(r"<[^>]+>", " ", html)
        return ""
    return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "replace")


def _hdr(v):
    return "".join(p.decode(c or "utf-8", "replace") if isinstance(p, bytes) else p for p, c in decode_header(v or ""))


def main():
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    user, pw = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS")
    if not (user and pw):
        print("Set SMTP_USER and SMTP_PASS (Gmail app password) in .env first.")
        return
    box = imaplib.IMAP4_SSL(os.environ.get("IMAP_HOST", "imap.gmail.com"))
    box.login(user, pw)
    box.select("INBOX")
    since = time.strftime("%d-%b-%Y", time.localtime(time.time() - 7 * 86400))
    _, ids = box.search(None, "UNSEEN", "SINCE", since)          # only recent unread mail, so it stays fast
    os.makedirs("inbox", exist_ok=True)
    saved = skipped = 0
    for i in ids[0].split():
        _, data = box.fetch(i, "(BODY.PEEK[])")                  # PEEK: unrelated mail stays unread
        msg = email.message_from_bytes(data[0][1])
        subject, sender = _hdr(msg.get("Subject")), _hdr(msg.get("From"))
        body = re.sub(r"(?m)^>.*$", "", _text(msg))            # drop quoted replies
        body = re.split(r"(?m)^--\s*$|^On .+ wrote:$", body)[0].strip()
        hits = {w.lower() for w in WORDS.findall(subject + " " + body)}
        if msg.get("List-Unsubscribe") or len(hits) < 2 or "Hackathon Planner login code" in subject:
            # newsletters/promotions and mails with fewer than 2 planning words are not event messages
            skipped += 1
            continue
        name = re.sub(r"\s*<[^>]+>", "", sender).strip() or sender
        try:
            date = parsedate_to_datetime(msg.get("Date")).strftime("%d %b")
        except Exception:                                      # noqa: BLE001
            date = ""
        fn = os.path.join("inbox", f"mail_{time.strftime('%H%M%S')}_{i.decode()}.txt")
        with open(fn, "w", encoding="utf-8") as fh:
            fh.write(f"{name}, email | {date}\n{subject}. {body}\n")
        box.store(i, "+FLAGS", "\\Seen")
        saved += 1
        print(f"saved {fn}  ({name}: {subject[:60]})")
    box.logout()
    print(f"{saved} planning email(s) saved to inbox/, {skipped} unrelated skipped. Now run: python main.py")


if __name__ == "__main__":
    main()
