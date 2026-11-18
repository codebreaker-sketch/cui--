"""The ONLY place a model is used: understanding raw messages (English / Roman Urdu).

Design: code finds every number in a message and tags it (#1, #2 ...). The model
only LABELS what each tagged number means (e.g. "#2 students"). The value itself is
always taken from the message by code, so a small model can never invent or mistype
a figure, and its reply stays very short (few tokens).
"""
import re

SYSTEM = """You label numbers in ONE event-planning message (English or Roman Urdu). Each number is tagged like 150(#2).
Reply ONLY with lines. First line: M | <sender> | <role> | <MM-DD or ->
role: authority (dean/admin/organiser), finance, venue, caterer, judging (coordinator), judge, student, other
Then one line per tagged number: #<n> <label>
labels: students | team_size | hours | budget | staff | judges | judge_fee | judge_minutes_per_team | judge_max_teams | judges_per_team | start_time | end_time | venue_seats <venue name> | venue_price <venue name> | food_price <basic|standard|premium> | spent <item> | request <item> | provides <food|seats|judges> | break_minutes <name> | extra_people | surcharge_pct <venue|food|all> | max_cost <item> | contingency_pct | date | ignore
budget = ONLY the event's total budget. food_price = price per head of a meal/box. spent = already paid/ordered from budget. request = a wish not yet approved. provides = a count someone says they will supply or has ordered.
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
Example: "Caterer: Biryani box Rs 900(#1) per head, simple wala Rs 600(#2). Already paid: banners Rs 5,000(#3). Students ask: photographer for Rs 20,000(#4)?"
M | Caterer | caterer | -
#1 food_price standard
#2 food_price basic
#3 spent banners
#4 request photographer"""

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
         "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
         "fifty": 50, "hundred": 100, "teen": 3, "char": 4, "panch": 5, "das": 10, "bees": 20, "pachas": 50}
NUM_RE = re.compile(
    r"(?i)\b(\d{1,2}:\d{2}\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm)\b|\d[\d,]*(?:\.\d+)?\s*(?:lakh|lac|k)?\b|"
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


def tag(text):
    """Returns (tagged_text, {n: value})."""
    vals, out, last, n = {}, [], 0, 0
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
        end = m.start(1) + len(m.group(1).rstrip())
        out.append(text[last:end] + f"(#{n})")
        last = end
    out.append(text[last:])
    return "".join(out), vals


def _none(s):
    s = (s or "").strip()
    return None if s.lower() in ("", "-", "none", "null", "n/a") else s


def parse_one(reply, vals, mid):
    cur = {"id": mid, "from": "?", "role": "other", "date": None, "rel": True, "f": []}
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
    if not cur["f"]:
        cur["rel"] = False
    return cur


def read(blocks, first_id, tracer):
    """One small call per message: a small model stays accurate on short inputs,
    and the identical system prompt is cached by the model server."""
    out = []
    for i, b in enumerate(blocks):
        mid = first_id + i
        tagged, vals = tag(b)
        if not vals and len(b) < 25:
            pass
        reply = tracer.call("reading", SYSTEM, f"Message:\n{tagged}")
        m = parse_one(reply, vals, mid)
        m["text"] = b
        out.append(m)
    return out
