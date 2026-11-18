"""Deterministic planner + validator. No model calls: arithmetic is code.

Planner: from the fact 'world' it derives headcount, picks the cheapest valid venue,
the best food tier and optional extras that still fit the budget (small exhaustive
search), builds a timed schedule, sizes the judging panel and the budget.

Validator: the six checks the organisers grade on, each with a plain reason.
"""
import itertools
import json
import math
import os
import re

from .facts import _norm

POL = json.load(open(os.path.join(os.path.dirname(__file__), "..", "policies.json"), encoding="utf-8"))


def _v(w, k, default=None):
    x = w["set"].get(k)
    return x["v"] if x else default


def _src(w, k):
    x = w["set"].get(k)
    return x["msg"] if x else None


def _hm(s):
    m = re.match(r"(\d{1,2})[:.](\d{2})\s*(am|pm)?", str(s or "").strip().lower())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if m.group(3) == "pm" and h < 12:
        h += 12
    if m.group(3) == "am" and h == 12:
        h = 0
    return h * 60 + mi


def _fmt(mins):
    h, m = divmod(int(mins), 60)
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}"


def _rnd(x):
    r = POL["slot_round_min"]
    return int(round(x / r) * r)


def headcount(w):
    students = _v(w, "students")
    team_size = _v(w, "team_size") or POL["default_team_size"]
    teams = math.ceil(students / team_size) if students else 0
    max_teams = _v(w, "judge_max_teams")
    per_team = _v(w, "judge_min_per_team") or POL["default_judge_min_per_team"]
    jpt = _v(w, "judges_per_team") or 1
    if not max_teams:
        max_teams = max(1, POL["default_judging_window_min"] // per_team)
    judges_needed = math.ceil(teams * jpt / max_teams) if teams else 0
    staff = _v(w, "staff") or 0
    extra = sum(n["v"] or 0 for n in w["needs"] if n["kind"] == "extra_people")
    return {"students": students, "team_size": team_size, "teams": teams, "judges_needed": judges_needed,
            "judges_per_team": jpt, "max_teams_per_judge": max_teams, "min_per_team": per_team,
            "staff": staff, "extra": extra,
            "people": (students or 0) + judges_needed + staff + extra}


def _surcharge(w, what):
    pct = 0
    for n in w["needs"]:
        if n["kind"] == "surcharge" and n["v"]:
            tgt = (n.get("what") or "all").lower()
            if tgt in ("all", what) or what in tgt:
                pct += n["v"]
    return pct


def _caps(w):
    return {(n.get("what") or "").lower(): n["v"] for n in w["needs"] if n["kind"] == "max_cost" and n["v"]}


def _venue_ok(w, v, people, reasons):
    req_feats = [str(n.get("what") or "").lower() for n in w["needs"]
                 if n["area"] == "venue" and n["kind"] == "require" and n.get("what")]
    forbid = [str(n.get("what") or "").lower() for n in w["needs"] if n["kind"] == "forbid" and n.get("what")]
    min_cap = max([n["v"] for n in w["needs"] if n["kind"] == "min_capacity" and n["v"]] + [people])
    name = v["name"]
    if not v.get("avail", True):
        reasons.append(f"{name}: not available"); return False
    if v.get("cap") is None or v.get("price") is None:
        reasons.append(f"{name}: capacity/price unknown"); return False
    if v["cap"] < min_cap:
        reasons.append(f"{name}: seats {v['cap']} < {min_cap} needed"); return False
    for f in req_feats:
        if not any(f in x or x in f for x in v.get("feat", [])):
            reasons.append(f"{name}: lacks required '{f}'"); return False
    for f in forbid:
        if f and (f in name.lower()):
            reasons.append(f"{name}: forbidden by a rule"); return False
    return True


def build(w):
    hc = headcount(w)
    people = hc["people"]
    budget = _v(w, "budget")
    contingency = (_v(w, "contingency_pct") or 0) / 100 * (budget or 0)
    caps = _caps(w)
    decisions = []

    # ---------- venue candidates
    vreasons, venues = [], []
    for v in w["venues"].values():
        if _venue_ok(w, v, people, vreasons):
            venues.append(v)
    venues.sort(key=lambda v: v["price"])

    # ---------- food candidates (preference order)
    pref = POL["food_tier_preference"]
    req_tiers = [str(n.get("what") or "").lower() for n in w["needs"]
                 if n["area"] == "food" and n["kind"] == "require"]
    foods = [f for f in w["foods"].values()
             if not any(t in pref and t != f["tier"] for t in req_tiers)]
    foods.sort(key=lambda f: pref.index(f["tier"]) if f["tier"] in pref else 99)

    judges_avail = _v(w, "judges_available")
    fee = _v(w, "judge_fee") or 0
    judges_used = hc["judges_needed"]
    judge_cost = judges_used * fee
    spent_total = sum(s["amt"] for s in w["spent"].values())
    reqs = list(w["reqs"].values())

    vs, fs = _surcharge(w, "venue"), _surcharge(w, "food")
    best, considered = None, 0
    for v in venues or [None]:
        for f in foods or [None]:
            vcost = round((v["price"] if v else 0) * (1 + vs / 100))
            fcost = round((f["pph"] * people if f else 0) * (1 + fs / 100))
            if caps.get("venue") and vcost > caps["venue"]:
                continue
            if caps.get("food") and fcost > caps["food"]:
                continue
            for r in range(len(reqs), -1, -1):
                for combo in itertools.combinations(reqs, r):
                    considered += 1
                    extras = sum(x["amt"] for x in combo)
                    total = spent_total + vcost + fcost + judge_cost + extras
                    fits = budget is None or total + contingency <= budget
                    tier_rank = pref.index(f["tier"]) if f and f["tier"] in pref else 99
                    score = (fits, v is not None, f is not None, -tier_rank, len(combo), -total)
                    if best is None or score > best[0]:
                        best = (score, v, f, combo, vcost, fcost, total)
    _, venue, food, combo, vcost, fcost, total = best
    decisions.append(f"optimizer compared {considered} venue x food x extras combinations")

    # ---------- budget lines
    lines = [{"item": f"Already spent: {s['item']}", "amt": s["amt"], "src": s["msg"]} for s in w["spent"].values()]
    if venue:
        lines.append({"item": f"Venue: {venue['name']}" + (f" (+{vs}% surcharge)" if vs else ""), "amt": vcost, "src": venue["msg"]})
    if food:
        lines.append({"item": f"Food: {food['name']} x {people} @ Rs {food['pph']:,}" + (f" (+{fs}%)" if fs else ""),
                      "amt": fcost, "src": food["msg"]})
    lines.append({"item": f"Judge honorarium: {judges_used} x Rs {fee:,}", "amt": judge_cost, "src": _src(w, "judge_fee")})
    for x in combo:
        lines.append({"item": f"Approved request: {x['item']}", "amt": x["amt"], "src": x["msg"]})
    declined = [{"item": x["item"], "amt": x["amt"], "src": x["msg"],
                 "why": "does not fit in the budget with essentials first"} for x in reqs if x not in combo]
    if contingency:
        lines.append({"item": f"Contingency reserve {_v(w, 'contingency_pct')}%", "amt": round(contingency), "src": _src(w, "contingency_pct")})
        total += round(contingency)

    # ---------- judging
    teams = hc["teams"]
    per_judge = math.ceil(teams * hc["judges_per_team"] / judges_used) if judges_used else 0
    judge_block = per_judge * hc["min_per_team"]
    judging = {"teams": teams, "judges_confirmed": judges_avail, "judges_used": judges_used,
               "judges_per_team": hc["judges_per_team"], "teams_per_judge": per_judge,
               "max_teams_per_judge": hc["max_teams_per_judge"], "min_per_team": hc["min_per_team"],
               "block_min": judge_block, "reserve_judges": max(0, (judges_avail or 0) - judges_used)}

    # ---------- schedule
    schedule, sched_notes = _schedule(w, judge_block, bool(combo))

    plan = {
        "headcount": hc, "people": people,
        "venue": {"name": venue["name"], "cap": venue["cap"], "price": venue["price"], "cost": vcost,
                  "feat": venue.get("feat", []), "src": venue["msg"]} if venue else None,
        "venue_rejected": vreasons,
        "food": {"name": food["name"], "tier": food["tier"], "pph": food["pph"], "boxes": people,
                 "cost": fcost, "src": food["msg"],
                 "alternatives": [{"tier": f["tier"], "pph": f["pph"], "cost": f["pph"] * people} for f in foods if f is not food]}
        if food else None,
        "judging": judging,
        "schedule": schedule, "schedule_notes": sched_notes,
        "budget": {"limit": budget, "lines": lines, "total": total,
                   "left": (budget - total) if budget is not None else None, "declined": declined,
                   "src": _src(w, "budget")},
        "notes": w["notes"], "needs": w["needs"], "decisions": decisions,
    }
    plan["checks"] = validate(w, plan)
    plan["valid"] = all(c["ok"] for c in plan["checks"])
    return plan


def _schedule(w, judge_block, has_closing_extra):
    hours = _v(w, "hours")
    start = _hm(_v(w, "start_time")) or _hm(POL["default_start"])
    end = _hm(_v(w, "end_time"))
    duration = (end - start) if end else int((hours or 0) * 60)
    notes = []
    breaks = [n for n in w["needs"] if n["area"] == "schedule" and n["kind"] == "break"]
    fixed = [n for n in w["needs"] if n["kind"] == "fixed" and n.get("v")]
    lunch_needed = bool(w["foods"])
    items = [("Opening & briefing", POL["opening_min"], "fixed", None)]
    middle = []
    if lunch_needed:
        middle.append(("Lunch", POL["lunch_min"], "meal", None))
    for b in breaks:
        middle.append((f"{(b.get('what') or 'Break').strip().capitalize()}", int(b["v"] or 15), "break", b.get("at")))
    for fx in fixed:
        middle.append((str(fx.get("what") or "Fixed item").capitalize(), int(fx["v"]), "fixed", fx.get("at")))
    tail = [("Judging (teams at tables, judges rotate)", judge_block, "judging", None),
            ("Closing & prizes" + (" + entertainment" if has_closing_extra else ""), POL["closing_min"], "fixed", None)]
    used = sum(x[1] for x in items + middle + tail)
    hacking = duration - used
    if hacking < 0:
        notes.append(f"activities need {used} min but event is only {duration} min")
    # one long build block, then meal/breaks (code freeze), then judging; anchors override
    h1 = hacking if hacking > 0 else 0
    anchored = [m for m in middle if m[3]]
    if anchored:
        target = _hm(anchored[0][3])
        if target is not None:
            pos = start + POL["opening_min"]
            idx = middle.index(anchored[0])
            pre = sum(x[1] for x in middle[:idx])
            want = target - pos - pre
            if 0 <= want <= hacking:
                h1 = want
            else:
                notes.append(f"could not place '{anchored[0][0]}' at {anchored[0][3]}")
    h2 = max(0, hacking - h1)
    seq = items + [("Build session" + (" 1" if h2 else ""), h1, "hack", None)] + middle + \
        [("Build session 2", h2, "hack", None)] + tail
    out, t = [], start
    for name, mins, kind, _ in seq:
        if mins <= 0:
            continue
        out.append({"start": _fmt(t), "end": _fmt(t + mins), "min": mins, "what": name, "kind": kind,
                    "t0": t, "t1": t + mins})
        t += mins
    return {"start": _fmt(start), "end": _fmt(start + duration), "duration_min": duration,
            "hacking_min": max(0, hacking), "slots": out}, notes


def validate(w, p):
    c = []
    hc, people = p["headcount"], p["people"]

    def add(name, ok, why):
        c.append({"check": name, "ok": bool(ok), "why": why})

    # 1 figures
    fig_ok = bool(hc["students"]) and p["food"] is not None and p["food"]["boxes"] == people
    add("Correct figures", fig_ok,
        f"{hc['students']} students / {hc['team_size']} = {hc['teams']} teams; feed & seat {people} "
        f"= {hc['students']} students + {hc['judges_needed']} judges + {hc['staff']} staff"
        + (f" + {hc['extra']} extra" if hc["extra"] else ""))
    # 2 budget
    b = p["budget"]
    add("Within budget", b["limit"] is not None and b["total"] <= b["limit"],
        f"Rs {b['total']:,} of Rs {b['limit']:,}" if b["limit"] is not None else "no budget stated")
    # 3 venue
    v = p["venue"]
    add("Venue fits", v is not None and v["cap"] >= people,
        f"{v['name']} seats {v['cap']} >= {people}" if v else "no venue meets every rule: " + "; ".join(p["venue_rejected"]))
    # 4 schedule
    s = p["schedule"]
    total = sum(x["min"] for x in s["slots"])
    breaks_needed = [n for n in w["needs"] if n["area"] == "schedule" and n["kind"] == "break"]
    hack_ok = s["hacking_min"] >= POL["min_hacking_min"]
    sched_ok = total == s["duration_min"] and s["duration_min"] > 0 and hack_ok and not p["schedule_notes"]
    add("Schedule valid", sched_ok,
        f"{len(s['slots'])} slots fill {total}/{s['duration_min']} min, {len(breaks_needed)} required break(s) placed, "
        f"{s['hacking_min']} min build time" + ("; " + "; ".join(p["schedule_notes"]) if p["schedule_notes"] else ""))
    # 5 judges
    j = p["judging"]
    j_ok = (j["judges_confirmed"] or 0) >= j["judges_used"] > 0 and j["teams_per_judge"] <= j["max_teams_per_judge"]
    add("Enough judges", j_ok,
        f"need {j['judges_used']} (= ceil({j['teams']} teams x {j['judges_per_team']} / {j['max_teams_per_judge']} max)), "
        f"{j['judges_confirmed']} confirmed")
    # 6 coverage
    missing = [a for a, x in (("venue", p["venue"]), ("food", p["food"]), ("schedule", s["slots"]),
                              ("judging", j["judges_used"]), ("budget", b["lines"])) if not x]
    add("All areas covered", not missing, "venue, schedule, food, judging, budget" if not missing else f"missing: {missing}")
    # quantity promises made by others must cover the people
    for q in w["qty"]:
        need = {"food": people, "venue_seats": people, "judges": j["judges_used"]}.get(q["item"])
        if need and q["v"] is not None and q["v"] < need:
            add(f"Quantity from message #{q['msg']}", False,
                f"{q['item']} {q['v']} < {need} required")
    return c
