"""Fact store: merges typed facts from messages into one 'world', keeping provenance.

Rules applied here (all plain code, all explained in the trace):
  R-STALE    an older message never overrides a newer fact (out-of-date messages)
  R-AUTH     core event settings can only be changed by someone with authority
             (a student society cannot change the budget or the headcount)
"""
import copy
import re

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

CORE_AUTH = {
    "students": {"authority"}, "team_size": {"authority"}, "hours": {"authority"},
    "staff": {"authority"}, "start_time": {"authority"}, "end_time": {"authority"},
    "budget": {"authority", "finance"}, "contingency_pct": {"authority", "finance"},
    "judges_available": {"authority", "judging"}, "judge_fee": {"authority", "judging", "finance"},
    "judge_min_per_team": {"authority", "judging"}, "judge_max_teams": {"authority", "judging"},
    "judges_per_team": {"authority", "judging"},
}
VENDOR_DENY = {"student"}   # who may never set prices / spending / quantities

KEY_AREA = {
    "students": "venue", "team_size": "judging", "hours": "schedule", "budget": "budget",
    "staff": "food", "judges_available": "judging", "judge_fee": "budget",
    "judge_min_per_team": "judging", "judge_max_teams": "judging", "judges_per_team": "judging",
    "start_time": "schedule", "end_time": "schedule", "contingency_pct": "budget",
}


# Which areas a setting feeds (people -> seats, boxes, judges, money). Used to predict and re-validate.
DEPENDS = {
    "students": {"venue", "food", "judging", "budget", "schedule"},
    "team_size": {"judging", "budget", "schedule"},
    "staff": {"venue", "food", "budget"},
    "judges_available": {"judging"},
    "judge_fee": {"judging", "budget"},
    "judge_min_per_team": {"judging", "schedule"},
    "judge_max_teams": {"judging", "venue", "food", "budget", "schedule"},
    "judges_per_team": {"judging", "venue", "food", "budget", "schedule"},
    "hours": {"schedule"}, "start_time": {"schedule"}, "end_time": {"schedule"},
    "budget": {"budget"}, "contingency_pct": {"budget"},
}


def parse_date(d):
    """'11-09' / '2026-11-09' / '9 Nov' / 'Nov 9' -> (month, day) or None."""
    if not d or not isinstance(d, str):
        return None
    s = d.strip().lower()
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return int(m.group(2)), int(m.group(3))
    m = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d{1,2})\s*([a-z]{3})", s) or re.search(r"([a-z]{3})[a-z]*\s*(\d{1,2})", s)
    if m:
        a, b = m.groups()
        if a.isdigit():
            return MONTHS.get(b[:3], 0), int(a)
        return MONTHS.get(a[:3], 0), int(b)
    return None


def _norm(s):
    s = re.sub(r"[^a-z0-9 ]", " ", str(s).lower())
    stop = {"the", "a", "an", "bill", "cost", "charges", "charge", "for", "of", "fee", "amount", "rs"}
    return " ".join(w for w in s.split() if w not in stop) or str(s).lower()


def _same(a, b):
    a, b = set(_norm(a).split()), set(_norm(b).split())
    return bool(a & b)


def _num(v):
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        t = v.replace(",", "")
        m = re.search(r"-?\d+(\.\d+)?", t)
        if m:
            x = float(m.group(0))
            if re.search(r"\d\s*k\b", t.lower()):
                x *= 1000
            return int(x) if x.is_integer() else x
    return None


def empty_world():
    return {"set": {}, "venues": {}, "foods": {}, "spent": {}, "reqs": {},
            "needs": [], "qty": [], "notes": [], "superseded": []}


def sort_key(msg, fallback_order):
    d = parse_date(msg.get("date"))
    return (d or (99, 99), fallback_order)


def apply_message(world, msg, tracer, strict):
    """Apply one message's facts to a COPY of world. Returns (new_world, problems, areas).
    strict=True for update messages (staleness & authority become rejections)."""
    w = copy.deepcopy(world)
    problems, areas = [], set()
    mid, role = msg["id"], (msg.get("role") or "other").lower()
    if strict and msg.get("role_by") == "model" and role != "other":
        tracer.note("reading", f"message #{mid}: no sender line, so the model's guess '{role}' gives no authority; "
                    "treated as an unknown sender")
        role = "other"
        msg["from"] = "unknown sender"
    date = parse_date(msg.get("date"))
    src = {"msg": mid, "date": date, "from": msg.get("from"), "role": role}

    def newer_than(existing):
        ed = existing.get("date")
        if date is None or ed is None:
            return True
        return tuple(date) >= tuple(ed)

    def supersede(kind, label, old, new_val):
        if not newer_than(old):
            if strict:
                problems.append(("R-STALE", f"{label}: message dated {date} is older than "
                                 f"message #{old['msg']} ({old.get('date')}); out of date"))
            else:
                w["superseded"].append({"msg": mid, "by": old["msg"], "what": label})
                tracer.note("reading", f"message #{mid} ({label}) is older than #{old['msg']}; kept #{old['msg']}")
            return False
        if old.get("value_repr") != new_val:
            w["superseded"].append({"msg": old["msg"], "by": mid, "what": label})
            tracer.note("reading", f"{label}: message #{mid} supersedes #{old['msg']} "
                        f"({old.get('value_repr')} -> {new_val})")
        return True

    for f in msg.get("f", []):
        t = f.get("t")
        if t == "set":
            k, v = f.get("k"), f.get("v")
            if k is None:
                continue
            if k in CORE_AUTH and role not in CORE_AUTH[k]:
                if strict or role in {"student", "other", "judge"}:
                    problems.append(("R-AUTH", f"'{msg.get('from')}' ({role}) has no authority to set {k}={v}"))
                    continue
            nv = v if k in ("start_time", "end_time") else _num(v)
            if nv is None:
                continue
            old = w["set"].get(k)
            if old and not supersede("set", k, old, nv):
                continue
            w["set"][k] = {"v": nv, "value_repr": nv, **src}
            areas.update(DEPENDS.get(k, {KEY_AREA.get(k, "budget")}))
        elif t == "venue":
            if role in VENDOR_DENY:
                problems.append(("R-AUTH", f"venue details from '{msg.get('from')}' ({role}) are not from the venue"))
                continue
            name = str(f.get("name") or "venue").strip()
            key = _norm(name)
            cur = w["venues"].get(key, {"name": name, "feat": [], "avail": True})
            if key in w["venues"] and not newer_than(cur):
                if strict:
                    problems.append(("R-STALE", f"venue {name}: older than message #{cur['msg']}"))
                continue
            for fld in ("cap", "price"):
                if f.get(fld) is not None and _num(f.get(fld)) is not None:
                    if strict and role not in ("venue", "authority") and cur.get(fld) is not None \
                            and cur[fld] != _num(f[fld]):
                        word = "seats" if fld == "cap" else "price Rs"
                        problems.append(("R-CONFLICT", f"{name}: this message says {word} {_num(f[fld]):,}, but the venue "
                                         f"itself said {word} {cur[fld]:,} (message #{cur.get('msg')}); "
                                         f"'{msg.get('from')}' ({role}) cannot change venue facts"))
                    if cur.get(fld) is not None and cur[fld] != _num(f[fld]):
                        tracer.note("venue", f"{name} {fld}: {cur[fld]} -> {_num(f[fld])} (message #{mid})")
                    cur[fld] = _num(f[fld])
            if f.get("feat"):
                cur["feat"] = sorted(set(cur.get("feat", [])) | {str(x).lower() for x in f["feat"]})
            if f.get("avail") is not None:
                cur["avail"] = bool(f["avail"])
            cur.update(src)
            w["venues"][key] = cur
            areas.add("venue")
        elif t == "food":
            if role in VENDOR_DENY:
                problems.append(("R-AUTH", f"food prices from '{msg.get('from')}' ({role}) are not from the caterer"))
                continue
            tier = (f.get("tier") or "standard").lower()
            pph = _num(f.get("pph"))
            if pph is None:
                continue
            old = w["foods"].get(tier)
            if old and not supersede("food", f"food {tier} price/head", old, pph):
                continue
            w["foods"][tier] = {"name": f.get("name") or tier, "tier": tier, "pph": pph,
                                "value_repr": pph, **src}
            areas.update({"food", "budget"})
        elif t == "spent":
            if role in VENDOR_DENY:
                problems.append(("R-AUTH", f"'{msg.get('from')}' ({role}) cannot commit budget spending"))
                continue
            item, amt = str(f.get("item") or "item"), _num(f.get("amt"))
            if amt is None:
                continue
            match = next((k for k in w["spent"] if _same(k, item)), None)
            if match:
                old = w["spent"][match]
                if not supersede("spent", f"spent '{old['item']}'", old, amt):
                    continue
                del w["spent"][match]
            w["spent"][_norm(item)] = {"item": item, "amt": amt, "value_repr": amt, **src}
            areas.add("budget")
        elif t == "req":
            item, amt = str(f.get("item") or "request"), _num(f.get("amt"))
            w["reqs"][_norm(item)] = {"item": item, "amt": amt or 0, **src}
            areas.add("budget")
        elif t == "need":
            area = f.get("area") if f.get("area") in ("venue", "schedule", "food", "judging", "budget") else "budget"
            if f.get("kind") == "use_venue" and role not in ("authority",) and strict:
                # still applied to this trial copy, so the rejection can also say whether the venue would fit
                problems.append(("R-AUTH", f"'{msg.get('from') or 'unknown sender'}' ({role}) cannot choose the venue "
                                 f"('{f.get('what')}'); only someone with authority can"))
            elif f.get("kind") == "use_venue" and role != "authority":
                w["notes"].append({"area": "venue", "text": f"{msg.get('from') or 'someone'} ({role}) suggests venue "
                                   f"'{f.get('what')}': not applied, only authority chooses the venue", **src})
                areas.add("venue")
                continue
            elif role in VENDOR_DENY | {"other"} and strict:
                problems.append(("R-AUTH", f"'{msg.get('from')}' ({role}) cannot impose a {area} rule"))
                continue
            need = {"area": area, "kind": f.get("kind") or "other", "what": f.get("what"),
                    "v": _num(f.get("v")) if f.get("v") is not None else None, "at": f.get("at"), **src}
            # same kind+what from a newer message replaces the old one
            w["needs"] = [n for n in w["needs"] if not (n["kind"] == need["kind"] and n["area"] == need["area"]
                                                        and _norm(n.get("what") or "") == _norm(need.get("what") or ""))]
            w["needs"].append(need)
            areas.add(area)
            if need["kind"] in ("extra_people", "surcharge", "max_cost"):
                areas.add("budget")
        elif t == "qty":
            w["qty"].append({"item": f.get("item"), "v": _num(f.get("v")), **src})
            areas.add({"food": "food", "venue_seats": "venue", "judges": "judging"}.get(f.get("item"), "budget"))
        elif t == "note":
            area = f.get("area") if f.get("area") in ("venue", "schedule", "food", "judging", "budget") else "budget"
            w["notes"].append({"area": area, "text": f.get("text"), **src})
            areas.add(area)
    return w, problems, areas
