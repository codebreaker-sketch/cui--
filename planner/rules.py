"""Code-first labeller: generic language patterns that need no model.

Why it exists: a small model mislabels obvious numbers ("150 students", "seats 250",
"Rs 850 per head"). Code labels those patterns itself, and its labels override the
model's. The model's labels are still used for any number code could not place, and for
constraints written without numbers. No facts from any pack are written here: only
general English / Roman Urdu wording.
Without it: the plan depends on how well a tiny model follows a format.
"""
import re

SPENT = r"already|ordered|paid|spent|bought|purchased|booked|\bbill\b|invoice|kharch|le li|order kar|de diy|came in at"
REQ = r"can we|could we|should we|\brequest|wish|would like|chahiye|kya hum|quote|le lein|optional|\?"
TIERS = {"basic": "basic", "simple": "basic", "economy": "basic", "sada": "basic", "saada": "basic",
         "standard": "standard", "normal": "standard",
         "premium": "premium", "deluxe": "premium", "special": "premium"}


def _sentence(text, pos):
    a = max(text.rfind(c, 0, pos) for c in ".!?;\n")
    ends = [i for i in (text.find(c, pos) for c in "!?;\n") if i >= 0]
    m = re.search(r"\.(\s|$|\")", text[pos:])          # a '.' inside 1,200.50 is not an end
    if m:
        ends.append(pos + m.start())
    return text[a + 1: min(ends) if ends else len(text)]


def _venue_name(seg):
    """'Hall A seats' / 'Auditorium 1 seats' / 'Seminar Hall ki capacity' -> name before the verb."""
    m = re.search(r"((?:the\s+)?[A-Z][\w'’-]*(?:\s+(?:[A-Z0-9][\w'’-]*|of|and))*)\s*(?:\(#\d+\))?\s*"
                  r"(?:seats|has|have|can|holds?|accommodates|ki|ka|is|costs?|at|capacity|rent)\b[^A-Z]*$", seg)
    if not m:
        return None
    name = re.sub(r"\(#\d+\)", "", m.group(1)).strip()
    return re.sub(r"^(the|only the|only)\s+", "", name, flags=re.I) or None


def label(text, vals, pos, role):
    """Returns ({n: (label, arg)}, [extra lines]) for what code is sure about."""
    out, extra = {}, []
    low = text.lower()
    last_venue = None
    # if the message names exactly one venue ("Hall B pay shift... us main 150 seats"), seats/prices without a
    # name next to them belong to it
    kinds = r"(?:Hall|Room|Auditorium|Lab|Block|Marquee|Lawn|Ballroom)"
    first = [(m.span(), m.group(0)) for m in re.finditer(r"\b" + kinds + r"\s+[A-Z0-9][\w-]*\b", text)]
    named = {g for _, g in first}
    for m in re.finditer(r"\b([A-Z][\w-]*)\s+(?:Hall|Room|Auditorium|Lab|Block|Centre|Center|Marquee|Lawn)\b", text):
        overlaps = any(a < m.end() and m.start() < b for (a, b), _ in first)
        if not overlaps and m.group(1).lower() not in ("hamain", "hamein", "humein", "the", "our", "we", "please", "ab"):
            named.add(m.group(0))
    only_venue = next(iter(named)) if len(named) == 1 else None
    for n in sorted(vals):
        v, p = vals[n], pos[n]
        tok = re.match(r"[A-Za-z]+\b|[\d:,.]+\s*(?:am|pm|lakh|lac|k)?", text[p:], re.I)
        end = p + (len(tok.group(0).rstrip()) if tok else 1)
        after = text[end:end + 40].lower()
        before = text[max(0, p - 50):p].lower()
        sent = _sentence(text, p)
        s = sent.lower()
        money = bool(re.search(r"(rs\.?|pkr|rupees?|₨)\s*$", before) or re.match(r"\s*(/-|rupees|rs\b|pkr)", after)
                     or (tok and re.search(r"(lakh|lac|k)$", tok.group(0).lower())))
        # a digit that is part of a name ("Auditorium 1 seats", "Room 3 has")
        if not money and isinstance(v, int) and v < 50 and re.search(r"[A-Z][a-z]+\s$", text[max(0, p - 20):p]) \
                and re.match(r"\s+(seats|has|have|is|at|ka|ki|can)\b", text[end:end + 12]):
            out[n] = ("ignore", "")
            continue
        if isinstance(v, str):                                      # a time like 09:00
            if re.search(r"start|begin|shuru|from|open", s) and not re.search(r"end|finish|khatam|till|until", before[-25:]):
                out[n] = ("start_time", "")
            elif re.search(r"end|finish|khatam|till|until|close", s):
                out[n] = ("end_time", "")
            continue
        if re.match(r"\s*(%|percent|fisad)", after):
            if re.search(r"conting|reserve|buffer|emergency", s):
                out[n] = ("contingency_pct", "")
            elif re.search(r"tax|gst|surcharge|service charge|fee|extra", s):
                tgt = "venue" if re.search(r"venue|hall|room|rent", s) else "food" if re.search(r"food|cater|lunch|box|meal", s) else "all"
                out[n] = ("surcharge_pct", tgt)
            continue
        if money and re.search(r"(not|instead of|pehle|old|previous|earlier)[\s,]*(rs\.?|pkr)?\s*$", before):
            out[n] = ("ignore", "")                 # "Rs 15,000, not Rs 10,000": the replaced figure
            continue
        if money:
            if re.search(r"per\s*(head|person|plate|box|meal)|/\s*head|fi\s*kas|har\s*band|each person", after[:25]) \
                    or role == "caterer":
                # tier: nearest tier word before the number in this sentence, else after it, else the item's name
                pre = s[:max(0, s.find(text[p:end].lower()))] if text[p:end].lower() in s else before
                hits = [(pre.rfind(w), t) for w, t in TIERS.items() if w in pre]
                tail = re.split(r"[.!?;\n]", after)[0]
                if re.search(r"\brs\b|pkr|\d", tail):          # a tier word followed by another price is that price's
                    tail = ""
                post = [t for w, t in TIERS.items() if re.search(r"\b" + w + r"\b", tail)]
                segs = [x for x in re.split(r"\brs\b|pkr|\d", pre) if re.search(r"[a-z]", x)]
                name = re.findall(r"[a-z]+", re.split(r"[,:;]", segs[-1])[-1] if segs else "")
                name = " ".join(w for w in name if w not in ("ab", "hoga", "the", "a", "and", "is", "now", "rates",
                                                              "update", "per", "head", "wala", "wali"))[-30:].strip()
                out[n] = ("food_price", max(hits)[1] if hits else post[0] if post else (name or "standard"))
            elif re.search(r"honorar|per judge|each judge|har judge|judge fee", s) and \
                    (role in ("judging", "authority", "finance") or "judge" in s):
                out[n] = ("judge_fee", "")
            elif re.search(r"budget|bajat", before[-30:] + " " + s) and not re.search(SPENT, s) and \
                    not re.search(r"from the", before[-25:]):      # who may set it: facts.py R-AUTH
                out[n] = ("budget", "")
            elif role == "venue" or re.search(r"\bseats\b|capacity|rent", s):
                name = last_venue or _venue_name(re.split(r"[.\n!?]", text[max(0, p - 120):p])[-1])
                if name:
                    out[n] = ("venue_price", name)
            elif role == "student" or (re.search(REQ, s) and not re.search(SPENT, s)):
                wish = re.search(r"(?:have|get|book|arrange|hire|need|want|add|le lein|mangwa)\s+(?:a |an |the |some )?"
                                 r"([a-z][a-z -]{2,30}?)(?=\s+(?:at|for|in|on|during|bhi|ka|ki)\b|[?.,!]|$)", low)
                out[n] = ("request", wish.group(1).strip() if wish else "")
            elif re.search(SPENT, low) and role in ("finance", "authority"):
                out[n] = ("spent", "")
            continue
        # plain counts. Roman Urdu / English "noun first": "students ki tadaad ab 165", "judges: 18", "staff hoga 12"
        nf = re.search(r"\b(students?|talba|bachon|bachay|participants?|judges?|staff|volunteers?)\b[\w\s]{0,6}?"
                       r"(?:\s*(?:ki|ka|ke)\s*(?:tadaad|tadad|number|ginti))?\s*(?:ab|now|is|hai|hain|hogi|hoga|=|:|to)?\s*"
                       r"(?:ab|now|kul|total)?\s*$", before)
        if nf and not re.match(r"\s*(students?|participants?|judges?|staff|volunteers?|teams?|minutes?|hours?|%)", after):
            noun = nf.group(1)
            lab = ("students" if noun.startswith(("stud", "talba", "bach", "partic")) else
                   "judges" if noun.startswith("judge") else "staff" if noun == "staff" else "extra_people")
            if lab != "judges" or role in ("judging", "authority"):
                out[n] = (lab, "volunteers" if lab == "extra_people" else "")
                continue
        if re.match(r"\s*(more |additional |extra |new |aur )?(students?|participants?|talib)", after):
            out[n] = ("students", "")
        elif re.search(r"teams? of\s*$", before) or re.match(r"\s*(-\s*)?(member|students?|people|log)\s*(per|in each|har)\s*team", after):
            out[n] = ("team_size", "")
        elif re.match(r"\s*-?\s*(hours?|hrs?|ghant\w*)\b", after) and not re.search(r"before|pehle|ago", after[:30]):
            out[n] = ("hours", "")
        elif re.match(r"\s*(staff|faculty|organi[sz]ers?)", after):
            out[n] = ("staff", "")
        elif re.match(r"\s*(volunteers?|guests?|helpers?|security|drivers?|media)", after):
            out[n] = ("extra_people", re.match(r"\s*(\w+)", after).group(1))
        elif re.match(r"\s*judges?\s*(per|for each|for every|on each|har|each)\s*(team|project|group)", after):
            out[n] = ("judges_per_team", "")
        elif re.match(r"\s*judges?", after) and role in ("judging", "authority") and \
                re.search(r"confirm|available|coming|arranged|on board|ready|aa rahe|have|now", s):
            out[n] = ("judges", "")
        elif re.match(r"\s*-?\s*(minutes?|mins?)", after) and re.search(r"per team|each team|har team|a team|per project", s):
            out[n] = ("judge_minutes_per_team", "")
        elif re.match(r"\s*-?\s*(minutes?|mins?)", after) and re.search(r"\b(break|namaz|prayer|tea|chai|rest|nap)\b", s):
            what = re.search(r"([a-z]+\s+)?(break|namaz|prayer|chai|tea)\b", re.sub(r"\b(minutes?|mins?|ka|ki|ke)\b", "", s))
            out[n] = ("break_minutes", " ".join(what.group(0).split()) if what else "break")
        elif re.search(r"(at most|no more than|max(imum)?|up to|zyada se zyada|only)\s*$", before) and \
                re.match(r"\s*teams?", after):
            out[n] = ("judge_max_teams", "")
        elif re.match(r"\s*judges?\s*(per|for each|har)\s*team", after):
            out[n] = ("judges_per_team", "")
        elif (re.search(r"(\bseats?|capacity( of| is)?|accommodates?|holds?)\s*(only|just|sirf|bas|about|around|up to|now)?\s*$",
                        before) or
              re.match(r"\s*(seats|seat capacity|log ki capacity)", after)) and (role == "venue" or "seat" in s):
            name = only_venue or _venue_name(re.split(r"[.\n!?]", text[max(0, p - 120):p])[-1])
            if name:
                out[n] = ("venue_seats", name)
                last_venue = name
        elif re.match(r"\s*(boxes|box|meals?|plates?|packets?|servings?|portions?|lunch\w*)", after) and not money:
            out[n] = ("provides", "food")
    # one unnamed meal option in a message is the standard option ("Biryani Rs 850 per head")
    tiers = set(TIERS.values())
    food = [k for k, (l, a) in out.items() if l == "food_price"]
    unnamed = [k for k in food if out[k][1] not in tiers]
    if unnamed and not any(out[k][1] == "standard" for k in food):
        out[unnamed[0]] = ("food_price", "standard")
    # "24 more students ... total is now 144": when one setting is stated twice, drop the change-amount
    delta = re.compile(r"more|additional|extra|dropped|drop out|cancel|left|fewer|less|kam|zyada|aur|backed out|withdr")
    for lab in ("students", "judges", "staff", "hours"):
        ns = [k for k, (l, _) in out.items() if l == lab]
        if len(ns) > 1:
            for k in ns:
                near = text[max(0, pos[k] - 15):pos[k] + 35].lower()
                if delta.search(near) and len([x for x in ns if out[x][0] == lab]) > 1:
                    out[k] = ("ignore", "")
    # constraints written without numbers
    for sent in re.split(r"[.!?\n]", text):
        m = re.search(r"(venue|hall|room|place|jagah)\b.{0,25}?\b(must|should|needs? to|has to|zaroor)\s+(have|be|hon?a?)\s+"
                      r"(?:a |an |the )?([a-z][\w -]{2,40})", sent, re.I)
        if m:
            extra.append(f"require venue | {m.group(4).strip().lower()}")
        for m in re.finditer(r"((?:only\s+)?(?:the\s+)?[A-Z][\w'’-]*(?:\s+(?:[A-Z0-9][\w'’-]*|and|&|,))*)\s+(?:has|have|offers?|comes? with)\s+"
                             r"(?:a |an |the )?([a-z][\w -]{2,40})", sent):
            if role == "venue":
                names = re.sub(r"^(only\s+)?(the\s+)?", "", m.group(1), flags=re.I)
                extra.append(f"feature {names} | {m.group(2).strip().lower()}")
        m = re.search(r"([A-Z][\w'’-]*(?:\s+[A-Z0-9][\w'’-]*)*)\s+(?:is|are)\s+(?:not available|unavailable|booked|closed|"
                      r"under renovation|out of service)", sent)
        if m:
            extra.append(f"unavailable {m.group(1)}")
        # a venue DECISION: "shift to Hall B", "move the event to Hall C", "Hall B pay shift karna chahiye"
        NAME = r"([A-Z][\w'’-]*(?:\s+[A-Z0-9][\w'’-]*)*)"
        m = re.search(r"\b(?:shift|move|switch|change|relocate|book|use|go with|take)\w*\s+(?:the\s+)?(?:event\s+|venue\s+|hackathon\s+)?"
                      r"(?:to|into|in|for|ko)?\s*(?:the\s+)?" + NAME, sent) or \
            re.search(NAME + r"\s+(?:pay|par|pe|mein|main|men|ko|me)\s+(?:shift|move|chal|le|book|rakh|kar|hona|ho)", sent) or \
            re.search(NAME + r"\s+(?:book|le|rakh|final)\s*(?:kar|karo|karein|lo|lein|kiya|ho)", sent, re.I)
        if m:
            name = re.sub(r"(?i)^((the|we|i|our|please|hamain|hamein|humein|hum|ab|now|so|then|let's|lets|kindly)\s+)+",
                          "", m.group(1).strip())
            if name and not re.fullmatch(r"(?i)the|we|i|our|it|this|that|please|hamain|hamein|humein", name):
                extra.append(f"choose {name}")
        elif only_venue and re.search(r"(?i)\b(shift|move|switch|relocate|go)\w*\s+(there|wahan|wahaan|udhar|us mein|usme|to it)\b", sent):
            extra.append(f"choose {only_venue}")              # "Hall B ... please shift there"
    return out, extra
