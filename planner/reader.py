"""The ONLY place a model is used: turning raw human messages (English / Roman Urdu)
into typed facts. Everything after this is plain, checkable code.

Why: language needs a model; arithmetic does not. One call per run keeps tokens low.
"""
import json
import re

from . import llm

SYSTEM = """You extract event-planning facts from messages (English or Roman Urdu). Output JSON only.
Return {"m":[{"id":int,"from":str,"role":R,"date":"MM-DD" or null,"rel":bool,"f":[facts]}]} one entry per message, in input order.
R is one of: authority (dean/admin/organiser/university), finance, venue, caterer, judging (judging coordinator), judge, student, other.
rel=false if the message has no planning fact (chit-chat, a person running late, greetings); then f=[].
Fact shapes (numbers as plain numbers, Rs amounts as integers, use only what the message says):
{"t":"set","k":K,"v":num|str}  K: students, team_size, hours, budget, staff, judges_available, judge_fee, judge_min_per_team, judge_max_teams, judges_per_team, start_time ("HH:MM" 24h), end_time, contingency_pct
{"t":"venue","name":str,"cap":int,"price":int,"feat":[short lowercase words e.g. "generator","projector","wheelchair"],"avail":true|false}  only include keys stated
{"t":"food","name":str,"tier":"basic"|"standard"|"premium","pph":int}  price per head
{"t":"spent","item":str,"amt":int}  money already spent/ordered from the budget
{"t":"req","item":str,"amt":int}  optional request/wish, not yet approved
{"t":"need","area":A,"kind":"break"|"require"|"min_capacity"|"max_cost"|"extra_people"|"surcharge"|"forbid"|"fixed"|"other","what":str,"v":num|null,"at":"HH:MM"|null}
   break: v=minutes; require: what=feature the venue/food must have; extra_people: v=count of extra people to feed/seat; surcharge: v=percent, what=venue|food|all; max_cost: v=Rs cap, what=item; fixed: what=activity, v=minutes, at=start time; forbid: what=thing not allowed
{"t":"qty","item":"food"|"venue_seats"|"judges"|str,"v":int}  a count someone says they will provide/order
{"t":"note","area":A,"text":str}  any other constraint, in a few words
A is one of: venue, schedule, food, judging, budget.
"""


def _strip(text):
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    return m.group(0) if m else text


def split_messages(raw):
    """Split a pack file into messages; keep each message's text exactly as given.
    Prefers explicit separators (--- lines, or lines starting '1.' / '#1' / 'Message 1'),
    otherwise blank lines."""
    text = raw.replace("\r\n", "\n").strip()
    if re.search(r"(?m)^\s*(-{3,}|={3,})\s*$", text):
        parts = re.split(r"(?m)^\s*(?:-{3,}|={3,})\s*$", text)
    else:
        marker = r"(?m)^(?=\s*(?:#\s*\d+\b|\d+\s*(?:[.)\]|]|:(?!\d))|\[\d+\]|message\s*\d+\b))"
        starts = re.findall(marker, text, flags=re.I)
        if len(starts) >= 2:
            parts = re.split(marker, text, flags=re.I)
        else:
            parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def read(blocks, first_id, tracer):
    numbered = "\n".join(f"[{first_id + i}] {b}" for i, b in enumerate(blocks))
    user = f"Messages:\n{numbered}"
    text = tracer.call("reading", SYSTEM, user)
    try:
        data = json.loads(_strip(text))
    except json.JSONDecodeError:
        tracer.note("reading", "model output was not valid JSON; asking once more")
        text = tracer.call("reading", SYSTEM, user + "\nReturn valid JSON only.")
        data = json.loads(_strip(text))
    msgs = data.get("m") or data.get("messages") or []
    by_id = {}
    for i, m in enumerate(msgs):
        mid = m.get("id")
        if not isinstance(mid, int) or not (first_id <= mid < first_id + len(blocks)):
            mid = first_id + i
        m["id"] = mid
        by_id[mid] = m
    out = []
    for i, b in enumerate(blocks):
        mid = first_id + i
        m = by_id.get(mid, {"id": mid, "from": "?", "role": "other", "date": None, "rel": False, "f": []})
        m["text"] = b
        m["f"] = [f for f in (m.get("f") or []) if isinstance(f, dict) and f.get("t")]
        out.append(m)
    return out
