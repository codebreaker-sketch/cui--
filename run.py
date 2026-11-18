"""ONE command for everything:   python run.py <messages.txt>

 * No saved plan yet, or the file holds a whole pack (4+ messages) -> plan from scratch.
 * Otherwise the file holds new message(s) -> update the existing plan.

Pipeline:  read (1 model call) -> merge facts (code) -> plan (code) -> validate (code)
           -> accept or reject each message with a rule + reason -> save state, trace, UI.
"""
import copy
import json
import os
import re
import sys
import time

from planner import facts as F
from planner import plan as P
from planner import reader, report, ui
from planner.llm import LLMError
from planner.trace import Tracer

STATE = os.path.join("state", "state.json")
OUT = "out"
PACK_MIN = 4


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def save_state(st):
    os.makedirs("state", exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=1)


def area_diff(old, new):
    if not old:
        return ["venue", "schedule", "food", "judging", "budget"]
    ch = []
    if (old.get("venue") or {}).get("name") != (new.get("venue") or {}).get("name") or \
            (old.get("venue") or {}).get("cost") != (new.get("venue") or {}).get("cost"):
        ch.append("venue")
    if [s["what"] + s["start"] for s in old["schedule"]["slots"]] != [s["what"] + s["start"] for s in new["schedule"]["slots"]]:
        ch.append("schedule")
    if json.dumps(old.get("food"), sort_keys=True) != json.dumps(new.get("food"), sort_keys=True):
        ch.append("food")
    if json.dumps(old["judging"], sort_keys=True) != json.dumps(new["judging"], sort_keys=True):
        ch.append("judging")
    if json.dumps(old["budget"], sort_keys=True) != json.dumps(new["budget"], sort_keys=True):
        ch.append("budget")
    return ch


def failed(plan):
    return [f"{c['check']}: {c['why']}" for c in plan["checks"] if not c["ok"]]


def full_run(raw, src_name):
    t0 = time.time()
    tr = Tracer(f"FULL RUN of '{src_name}'")
    tr.header()
    blocks = reader.split_messages(raw)
    tr.note("reading", f"file split into {len(blocks)} messages (text kept exactly as given)")
    msgs = reader.read(blocks, 1, tr)
    order = sorted(range(len(msgs)), key=lambda i: F.sort_key(msgs[i], i))
    world, rejected = F.empty_world(), []
    for i in order:
        m = msgs[i]
        if not m.get("rel") and not m["f"]:
            m["status"] = "ignored"
            m["reason"] = "no planning fact (irrelevant to venue/schedule/food/judging/budget)"
            tr.note("reading", f"message #{m['id']} ignored: {m['reason']}")
            continue
        world, problems, areas = F.apply_message(world, m, tr, strict=False)
        m["areas"] = sorted(areas)
        m["status"] = "accepted"
        for rule, why in problems:
            tr.reject(m["id"], rule, why)
            rejected.append({"msg": m["id"], "rule": rule, "reason": why, "text": m["text"]})
            m["status"] = "partly rejected"
            m["reason"] = why
    plan = P.build(world)
    # quantities promised by others that do not cover everyone -> reject that message
    for q in list(world["qty"]):
        bad = [c for c in plan["checks"] if c["check"] == f"Quantity from message #{q['msg']}" and not c["ok"]]
        if bad:
            why = bad[0]["why"]
            tr.reject(q["msg"], "R-COVER", f"{why}; plan keeps {plan['people']}")
            rejected.append({"msg": q["msg"], "rule": "R-COVER", "reason": why,
                             "text": next(m["text"] for m in msgs if m["id"] == q["msg"])})
            world["qty"].remove(q)
            for m in msgs:
                if m["id"] == q["msg"]:
                    m["status"], m["reason"] = "rejected", why
    plan = P.build(world)
    for d in plan["decisions"]:
        tr.note("budget", d)
    for x in plan["budget"]["declined"]:
        tr.note("budget", f"request '{x['item']}' (Rs {x['amt']:,}, message #{x['src']}) declined: {x['why']}")
    for c in plan["checks"]:
        tr.note("budget" if "budget" in c["check"].lower() else "venue" if "Venue" in c["check"] else
                "schedule" if "Schedule" in c["check"] else "judging" if "judge" in c["check"].lower() else "food",
                f"CHECK {'PASS' if c['ok'] else 'FAIL'} - {c['check']}: {c['why']}")
    st = {"messages": msgs, "world": world, "plan": plan, "rejected": rejected,
          "next_call_no": tr.next_no, "tokens_total": tr.tokens["total"],
          "runs": [{"label": tr.run_label, "calls": tr.calls, "tokens": tr.tokens, "secs": round(time.time() - t0, 1),
                    "areas_replanned": area_diff(None, plan), "model_areas": ["reading"], "events": tr.events}],
          "trace_lines": []}
    tr.footer(st["tokens_total"])
    st["trace_lines"] = tr.lines
    return st


def update_run(st, raw, src_name):
    t0 = time.time()
    tr = Tracer(f"UPDATE with '{src_name}'", st["next_call_no"])
    tr.header()
    blocks = reader.split_messages(raw)
    if len(blocks) > 1:
        blocks = ["\n\n".join(blocks)] if len(blocks) < PACK_MIN else blocks
    first = len(st["messages"]) + 1
    msgs = reader.read(blocks, first, tr)
    old_plan = st["plan"]
    world, plan = st["world"], st["plan"]
    replanned, predicted = set(), set()
    for m in msgs:
        if not m.get("rel") and not m["f"]:
            m["status"], m["reason"] = "ignored", "no planning fact"
            tr.note("reading", f"message #{m['id']} ignored: no planning fact; plan unchanged")
            st["messages"].append(m)
            continue
        new_world, problems, areas = F.apply_message(world, m, tr, strict=True)
        predicted |= areas
        m["areas"] = sorted(areas)
        tr.note("reading", f"message #{m['id']} touches: {', '.join(sorted(areas)) or 'nothing'}")
        if problems:
            for rule, why in problems:
                tr.reject(m["id"], rule, why)
            m["status"], m["reason"] = "rejected", problems[0][1]
            st["rejected"].append({"msg": m["id"], "rule": problems[0][0], "reason": problems[0][1], "text": m["text"]})
            st["messages"].append(m)
            continue
        cand = P.build(new_world)
        if not cand["valid"] and plan["valid"]:
            reasons = failed(cand)
            rule = "R-COVER" if any(r.startswith("Quantity") for r in reasons) else "R-VALID"
            why = "accepting it would break the plan -> " + " | ".join(reasons)
            tr.reject(m["id"], rule, why)
            tr.note("budget", "plan kept unchanged (still valid)")
            m["status"], m["reason"] = "rejected", why
            st["rejected"].append({"msg": m["id"], "rule": rule, "reason": why, "text": m["text"]})
            st["messages"].append(m)
            continue
        changed = area_diff(plan, cand)
        replanned |= set(changed)
        world, plan = new_world, cand
        m["status"] = "accepted"
        tr.note("budget", f"message #{m['id']} accepted; areas re-planned by code: {', '.join(changed) or 'none (no effect)'}")
        st["messages"].append(m)
    for c in plan["checks"]:
        if not c["ok"]:
            tr.note("budget", f"CHECK FAIL - {c['check']}: {c['why']}")
    tr.note("budget", f"all checks: {'PASS' if plan['valid'] else 'SOME FAIL'}; total Rs {plan['budget']['total']:,}")
    st["world"], st["plan"] = world, plan
    st["next_call_no"] = tr.next_no
    st["tokens_total"] += tr.tokens["total"]
    st["runs"].append({"label": tr.run_label, "calls": tr.calls, "tokens": tr.tokens, "secs": round(time.time() - t0, 1),
                       "areas_predicted": sorted(predicted), "areas_replanned": sorted(replanned),
                       "model_areas": ["reading"], "events": tr.events, "diff": _money_diff(old_plan, plan)})
    tr.footer(st["tokens_total"])
    st["trace_lines"] += [""] + tr.lines
    return st


def _money_diff(a, b):
    return {"total": [a["budget"]["total"], b["budget"]["total"]],
            "venue": [(a.get("venue") or {}).get("name"), (b.get("venue") or {}).get("name")],
            "food": [(a.get("food") or {}).get("cost"), (b.get("food") or {}).get("cost")]}


def main():
    if len(sys.argv) != 2:
        print("usage: python run.py <messages.txt>")
        sys.exit(1)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    path = sys.argv[1]
    with open(path, encoding="utf-8-sig") as fh:
        raw = fh.read()
    st = load_state()
    n = len(reader.split_messages(raw))
    try:
        if st is None or n >= PACK_MIN:
            if st is not None:
                print(f"(file has {n} messages -> treated as a new pack; starting a fresh plan)")
            st = full_run(raw, os.path.basename(path))
        else:
            st = update_run(st, raw, os.path.basename(path))
    except LLMError as e:
        print(f"MODEL ERROR: {e}\nPlan not changed.")
        sys.exit(2)
    save_state(st)
    os.makedirs(OUT, exist_ok=True)
    report.print_plan(st)
    report.write_files(st, OUT)
    ui.write(st, os.path.join(OUT, "index.html"))
    print(f"\nSaved: {OUT}/plan.txt  {OUT}/trace.txt  {OUT}/final_report.txt  UI: {OUT}/index.html")


if __name__ == "__main__":
    main()
