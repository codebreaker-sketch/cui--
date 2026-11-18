"""The ONLY place a model is used: understanding raw messages (English / Roman Urdu).

Design: code finds every number in a message and tags it (#1, #2 ...). The model
only LABELS what each tagged number means (e.g. "#2 students"). The value itself is
always taken from the message by code, so a small model can never invent or mistype
a figure, and its reply stays very short (few tokens).
"""
import re

SYSTEM = """You label numbers in ONE message about planning a hackathon (English or Roman Urdu). Each number is tagged like 150(#2).
Reply ONLY with lines. First line: M | <sender> | <role> | <MM-DD or ->
role: authority (dean/admin/organiser), finance, venue, caterer, judging (coordinator), judge (one judge), student, other
Then one line per tagged number: #<n> <label>
labels: students | team_size | hours | budget | staff | judges | judge_fee | judge_minutes_per_team | judge_max_teams | judges_per_team | start_time | end_time | venue_seats <venue name> | venue_price <venue name> | food_price <basic|standard|premium> | spent <item> | request <item> | provides <food|seats|judges> | break_minutes <name> | extra_people <who> | surcharge_pct <venue|food|all> | max_cost <venue|food> | contingency_pct | ignore
budget = ONLY the event's total budget. food_price = price per head of a meal/box. spent = already paid/ordered/billed from the budget (a new bill for an item replaces the old one). request = a wish or quote not yet approved. provides = a count someone will supply/has ordered. ignore = anything else (delays, dates, phone numbers).
Extra lines only if stated:
feature <venue name> | <feature>
unavailable <venue name>
require <venue|food> | <thing>
note <venue|schedule|food|judging|budget> | <short text>
If the message has no planning fact, write only the M line.
Example: "Registrar, 2 Nov: 90(#1) students, 3(#2) ghante. Chai break 10(#3) minute ka. Lab 5 seats 120(#4) at Rs 30,000(#5), Lab 5 has projector."
M | Registrar | authority | 11-02
#1 students
#2 hours
#3 break_minutes tea break
#4 venue_seats Lab 5
#5 venue_price Lab 5
feature Lab 5 | projector
Example: "Accounts: Paid from the event budget: banners Rs 5,000(#1), T-shirts Rs 40,000(#2). Society asks: photographer for Rs 20,000(#3)? Biryani Rs 900(#4) per head."
M | Accounts | finance | -
#1 spent banners
#2 spent T-shirts
#3 request photographer
#4 food_price standard"""

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
         "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
         "fifty": 50, "hundred": 100, "teen": 3, "char": 4, "panch": 5, "das": 10, "bees": 20, "pachas": 50}
NUM_RE = re.compile(
    r"(?i)\b(\d{1,2}:\d{2}\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm)\b|\d+(?:,\d{2,3})*(?:\.\d+)?\s*(?:lakh|lac|k)?\b|"
    + "|".join(sorted(WORDS, key=len, reverse=True)) + r")\b")
SET_LABELS = {"students": "students", "team_size": "team_size", "hours": "hours", "budget": "budget",
              "staff": "staff", "judges": "judges_available", "judge_fee": "judge_fee",
              "judge_minutes_per_team": "judge_min_per_team", "judge_max_teams": "judge_max_teams",
              "judges_per_team": "judges_per_team", "start_time": "start_time", "end_time": "end_time",
              "contingency_pct": "contingency_pct"}
ROLES = {"authority", "finance", "venue", "caterer", "judging", "judge", "student", "other"}
AREAS = {"venue", "schedule", "food", "judging", "budget"}


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


def _value(tok):
    t = tok.strip().lower()
    if re.match(r"^\d{1,2}:\d{2}|^\d{1,2}\s*(am|pm)$", t):
        m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if m.group(3) == "pm" and h < 12:
            h += 12
        return f"{h:02d}:{mi:02d}"
    if t in WORDS:
        return WORDS[t]
    x = float(re.sub(r"[^\d.]", "", t) or 0)
    if "lakh" in t or "lac" in t:
        x *= 100000
    elif t.endswith("k"):
        x *= 1000
    return int(x) if x.is_integer() else x


def tag(text, pos=None):
    """Returns (tagged_text, {n: value}); fills pos[n] = index of the number in text."""
    vals, out, last, n = {}, [], 0, 0
    pos = {} if pos is None else pos
    month = r"\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b"
    for m in NUM_RE.finditer(text):
        after = text[m.end():m.end() + 12].lower()
        if re.match(month, after) or (m.start() <= 2 and re.match(r"\s*[|.):\]]", after)):
            continue                     # dates and the message's own index are not facts
        before = text[:m.start()].split()
        if before and re.fullmatch(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?",
                                   before[-1].lower()):
            continue                     # "Nov 9" style dates
        n += 1
        vals[n] = _value(m.group(1))
        pos[n] = m.start(1)
        end = m.start(1) + len(m.group(1).rstrip())
        out.append(text[last:end] + f"(#{n})")
        last = end
    out.append(text[last:])
    return "".join(out), vals


MONTH_RE = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
# Generic vocabulary for WHO a sender is (not facts from any pack). Order matters: first match wins.
ROLE_WORDS = [
    ("judging", r"judging|jury|judges?\s*(co-?ordinator|panel|lead|head)|co-?ordinator.*judg"),
    ("judge", r"\bjudge\b"),
    ("finance", r"financ|accounts?\b|treasur|bursar|audit"),
    ("caterer", r"cater|kitchen|restaurant|bakery|dhaba|food\s*(vendor|supplier|service)|chef"),
    ("venue", r"\bhalls?\b|venue|hotel|auditorium|convention|banquet|marquee|event\s*(centre|center|space)"),
    ("student", r"student|society|club|participant|team\s*(lead|member)|volunteer"),
    ("authority", r"dean|registrar|principal|director|rector|\bvc\b|vice.?chancellor|admin|organi[sz]|"
                  r"office|chair|\bhod\b|head\s*of|management|committee|president|ceo|provost"),
]


def header(block):
    """Code (not the model) reads the sender line and the date, so they are never mis-typed.
    Returns (sender or None, 'MM-DD' or None, role or None)."""
    first = block.strip().splitlines()[0] if block.strip() else ""
    date = None
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", first)
    if m:
        date = f"{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    else:
        m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+" + MONTH_RE + r"\b", first, re.I) or \
            re.search(r"\b" + MONTH_RE + r"\.?\s+(\d{1,2})\b", first, re.I)
        if m:
            g = m.groups()
            day = next(x for x in g if x and x.isdigit())
            mon = next(x for x in g if x and not x.isdigit())
            date = f"{F_MONTHS[mon[:3].lower()]:02d}-{int(day):02d}"
    sender = None
    if "|" in first:
        parts = [p.strip() for p in first.split("|")]
        parts = [p for p in parts if p and not re.fullmatch(r"#?\s*\d+[.)]?", p)
                 and not re.search(r"\b\d{1,2}\s+" + MONTH_RE + r"|\b" + MONTH_RE + r"\s+\d|\d{4}-\d", p, re.I)]
        sender = parts[0] if parts else None
    else:
        m = re.match(r"\s*(?:#?\d+[.)]\s*)?(?:from\s*:\s*)?([A-Za-z][\w'’ .&()-]{1,40}?)\s*(?::|\bhere\b)", first, re.I)
        if m:
            sender = m.group(1).strip()
    probe = (sender or first[:60]).lower()
    role = next((r for r, pat in ROLE_WORDS if re.search(pat, probe)), None)
    return sender, date, role


F_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
SPENT_CUE = re.compile(r"(?i)already|ordered|paid|spent|bought|purchased|booked|\bbill\b|invoice|kharch|le li|"
                       r"order kar|de diy|came in at")
REQ_CUE = re.compile(r"(?i)can we|could we|should we|request|wish|would like|chahiye|kya hum|quote|maybe|optional")


def _item_before(text, pos):
    """Words just before a number, e.g. 'prizes Rs 100,000' -> 'prizes' (used when the model gives no item)."""
    seg = re.split(r"[.,;:!?\n(\"“]", text[max(0, pos - 40):pos])[-1]
    words = [w for w in re.findall(r"[A-Za-z]+", seg) if w.lower() not in ("rs", "pkr", "at", "for", "is", "of", "the", "a")]
    return " ".join(words[-3:]) or None


def _none(s):
    s = (s or "").strip()
    return None if s.lower() in ("", "-", "none", "null", "n/a") else s


def parse_one(reply, vals, mid, text="", pos=None):
    pos = pos or {}
    cur = {"id": mid, "from": "?", "role": "other", "date": None, "rel": True, "f": []}
    h_sender, h_date, h_role = header(text) if text else (None, None, None)
    spent_cue, req_cue = bool(SPENT_CUE.search(text)), bool(REQ_CUE.search(text))
    venues = {}

    def venue(name):
        key = re.sub(r"\s+", " ", (name or "venue").strip()).title()
        if key not in venues:
            venues[key] = {"t": "venue", "name": key, "feat": []}
            cur["f"].append(venues[key])
        return venues[key]

    for line in reply.splitlines():
        line = line.strip().strip("`").strip()
        if not line:
            continue
        low = line.lower()
        if line.startswith("M") and "|" in line:
            p = [x.strip() for x in line[1:].strip(" |").split("|")]
            cur["from"] = p[0] if p else "?"
            role = (p[1] if len(p) > 1 else "other").lower()
            cur["role"] = role if role in ROLES else "other"
            cur["date"] = _none(p[2]) if len(p) > 2 else None
            continue
        m = re.match(r"#\s*(\d+)\s*[:.\-]?\s*([a-z_]+)\s*(.*)", line, re.I)
        if m:
            n, label, arg = int(m.group(1)), m.group(2).lower(), m.group(3).strip(" |:-")
            if n not in vals:
                continue
            v = vals[n]
            role = h_role or cur["role"]
            # code guards against the most common small-model mislabels
            after = text[pos.get(n, 0):pos.get(n, 0) + 30].lower()
            before = text[max(0, pos.get(n, 0) - 45):pos.get(n, 0)].lower()
            money = bool(re.search(r"(rs\.?|pkr|rupees?|₨)\s*$", before) or
                         re.match(r"[\d,.]+\s*(/-|rupees|rs\b|pkr|lakh|lac|k\b)", after))
            units = re.match(r"[\d,.]+\s*(boxes|box|meals?|plates?|packets?|servings?|portions?|lunch\w*|"
                             r"people|persons|pax|log|banday|seats?|chairs?|judges?)\b", after)
            money = money or (not units and isinstance(v, (int, float)) and v >= 1000)
            if units and not money and label not in ("students", "staff", "judges", "venue_seats", "extra_people"):
                u = units.group(1)
                label, arg = "provides", ("seats" if u.startswith(("seat", "chair")) else
                                          "judges" if u.startswith("judge") else "food")
            elif label in ("budget", "spent", "request", "food_price", "judge_fee", "venue_price") and not money:
                label = "ignore"            # a money label on a number that is not money
            if label in ("budget", "spent", "request", "food_price") and (
                    role == "caterer" or re.search(r"per\s*(head|person|plate|box)|/\s*head|fi\s*kas|har\s*band", after)):
                label = "food_price"
                # tier = the tier word nearest BEFORE the number ("basic wala Rs 800"), else the model's word
                hits = [(before.rfind(t), t) for t in ("basic", "premium", "standard", "economy", "deluxe", "simple")
                        if t in before]
                if hits:
                    t = max(hits)[1]
                    arg = {"economy": "basic", "simple": "basic", "deluxe": "premium"}.get(t, t)
            elif label in ("budget", "spent") and role == "judging" and re.search(r"each|per\s*judge|har\s*judge|honorar", before + after):
                label = "judge_fee"
            if label == "budget" and not re.search(r"(?i)budget|all.in|total|kul|bajat", text):
                label = "request" if role == "student" or req_cue else "spent"
            if label == "budget" and role == "student":
                label = "request"
            if label == "budget" and spent_cue and sum(1 for x in reply.lower().split() if x == "budget") > 1:
                label = "spent"
            if label in ("spent", "request") and not arg:
                arg = _item_before(text, pos.get(n, 0)) or label
            if label == "spent" and role == "student":
                label = "request"
            if label == "break_minutes" and role in ("judge", "student"):
                cur["f"].append({"t": "note", "area": "schedule", "text": f"{arg or 'delay'}: {v} min (from {role}; not a planned break)"})
                continue
            if label == "ignore" or re.search(r"(?i)(\bnot\s*,?\s*|instead of|pehle|\bold|previous)\s*(rs\.?|pkr)?\s*$",
                                                text[max(0, pos.get(n, 0) - 16):pos.get(n, 0)]):
                continue                     # "Rs 15,000, not Rs 10,000": the replaced figure is not a fact
            if label in SET_LABELS:
                cur["f"].append({"t": "set", "k": SET_LABELS[label], "v": v})
            elif label == "venue_seats":
                venue(arg)["cap"] = v
            elif label == "venue_price":
                venue(arg)["price"] = v
            elif label == "food_price":
                tier = next((t for t in ("basic", "standard", "premium") if t in arg.lower()), "standard")
                cur["f"].append({"t": "food", "tier": tier, "pph": v, "name": f"{tier.capitalize()} box"})
            elif label in ("spent", "request"):
                cur["f"].append({"t": "spent" if label == "spent" else "req", "item": arg or label, "amt": v})
            elif label == "provides":
                item = "food" if "food" in arg.lower() or "box" in arg.lower() else \
                    "venue_seats" if "seat" in arg.lower() else "judges" if "judge" in arg.lower() else arg.lower()
                cur["f"].append({"t": "qty", "item": item, "v": v})
            elif label == "break_minutes":
                cur["f"].append({"t": "need", "area": "schedule", "kind": "break", "what": arg or "break", "v": v, "at": None})
            elif label == "extra_people":
                cur["f"].append({"t": "need", "area": "food", "kind": "extra_people", "what": arg or "extra", "v": v, "at": None})
            elif label == "surcharge_pct":
                cur["f"].append({"t": "need", "area": "budget", "kind": "surcharge", "what": (arg or "all").lower(), "v": v, "at": None})
            elif label == "max_cost":
                cur["f"].append({"t": "need", "area": "budget", "kind": "max_cost", "what": (arg or "").lower(), "v": v, "at": None})
            continue
        p = [x.strip() for x in line.split("|")]
        if low.startswith("feature"):
            names = re.split(r"\s*(?:,|\band\b|&)\s*", p[0][7:].strip())
            for nm in names:
                if nm and len(p) > 1:
                    venue(nm)["feat"].append(p[1].lower())
        elif low.startswith("unavailable"):
            venue(line[11:].strip())["avail"] = False
        elif low.startswith("require") and len(p) > 1:
            area = "food" if "food" in p[0].lower() else "venue"
            cur["f"].append({"t": "need", "area": area, "kind": "require", "what": p[1].lower(), "v": None, "at": None})
        elif low.startswith("note") and len(p) > 1:
            area = p[0][4:].strip().lower()
            cur["f"].append({"t": "note", "area": area if area in AREAS else "budget", "text": p[1]})
    # "Halls B and C have a generator" -> venues "B", "C": attach to "Hall B", "Hall C"
    full = [v for v in venues.values() if "cap" in v or "price" in v]
    for short in [v for v in venues.values() if "cap" not in v and "price" not in v]:
        tok = short["name"].lower().split()[-1] if short["name"].split() else ""
        target = next((v for v in full if v["name"].lower().split()[-1] == tok), None)
        if target and target is not short:
            target["feat"] = sorted(set(target["feat"]) | set(short["feat"]))
            if short.get("avail") is False:
                target["avail"] = False
            cur["f"].remove(short)
    if h_sender:
        cur["from"] = h_sender
    if h_role:
        cur["role"] = h_role
    if h_date:
        cur["date"] = h_date
    if not cur["f"]:
        cur["rel"] = False
    return cur


def read(blocks, first_id, tracer):
    """One small call per message (a small model stays accurate on short inputs).
    Calls run in parallel to stay inside the time limit; the trace keeps message order."""
    tagged = []
    for b in blocks:
        pos = {}
        t, vals = tag(b, pos)
        tagged.append((t, vals, pos))
    users = ["Message:\n" + t for t, _, _ in tagged]
    replies = tracer.call_many("reading", SYSTEM, users)
    out = []
    for i, (b, (t, vals, pos), reply) in enumerate(zip(blocks, tagged, replies)):
        m = parse_one(reply or "", vals, first_id + i, b, pos)
        m["text"] = b
        if reply is None:
            m["status_hint"] = "model call failed or timed out; message not read"
        out.append(m)
    return out
