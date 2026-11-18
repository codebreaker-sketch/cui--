"""ONE command for everything:   python main.py        (reads messages.txt)

 * No saved plan yet, or the file holds a whole NEW pack (4+ messages, none seen before)
   -> plan from scratch (full run, 120 s limit).
 * Otherwise the messages in the file that were not seen before are an UPDATE
   (60 s limit, at most 5 model calls). You may append to messages.txt or replace it.

Pipeline:  read (1 model call) -> merge facts (code) -> plan (code) -> validate (code)
           -> accept or reject each message with a rule + reason -> save state, trace, UI.
"""
import copy
import hashlib
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
INBOX = "messages.txt"
INBOX_DIR = "inbox"
PACK_MIN = 4
FULL_LIMIT_S, UPDATE_LIMIT_S, UPDATE_MAX_CALLS = 120, 60, 5


def fingerprint(block):
    return hashlib.sha1(" ".join(block.split()).lower().encode("utf-8")).hexdigest()[:16]


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


def full_run(blocks, src_name):
    t0 = time.time()
    tr = Tracer(f"FULL RUN of '{src_name}'", limit_s=FULL_LIMIT_S)
    tr.header()
    tr.note("reading", f"file split into {len(blocks)} messages (text kept exactly as given)")
    tr.note("reading", f"PREDICTION: {len(blocks)} model call(s), all tagged 'reading' (one per message); "
            "venue, schedule, food, judging, budget are planned by code with 0 model calls")
    msgs = reader.read(blocks, 1, tr)
    order = sorted(range(len(msgs)), key=lambda i: F.sort_key(msgs[i], i))
    world, rejected = F.empty_world(), []
    for i in order:
        m = msgs[i]
        if m.get("status_hint") and not m["f"]:
            m["status"], m["reason"] = "not read", m["status_hint"]
            tr.note("reading", f"message #{m['id']}: {m['status_hint']}")
            continue
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
          "seen": [fingerprint(m["text"]) for m in msgs],
          "next_call_no": tr.next_no, "tokens_total": tr.tokens["total"],
          "runs": [{"label": tr.run_label, "calls": tr.calls, "tokens": tr.tokens, "secs": round(time.time() - t0, 1),
                    "areas_replanned": area_diff(None, plan), "model_areas": ["reading"], "events": tr.events}],
          "trace_lines": []}
    tr.footer(st["tokens_total"])
    st["trace_lines"] = tr.lines
    return st


def update_run(st, blocks, src_name):
    t0 = time.time()
    tr = Tracer(f"UPDATE with '{src_name}'", st["next_call_no"], limit_s=UPDATE_LIMIT_S, max_calls=UPDATE_MAX_CALLS)
    tr.header()
    if len(blocks) > UPDATE_MAX_CALLS:      # never more than 5 calls: fold the overflow into the last call
        blocks = blocks[:UPDATE_MAX_CALLS - 1] + ["\n\n".join(blocks[UPDATE_MAX_CALLS - 1:])]
    tr.note("reading", f"PREDICTION (made before any model call): {len(blocks)} new message(s) -> {len(blocks)} "
            "model call(s), area tag 'reading' only. venue/schedule/food/judging/budget make 0 model calls; "
            "code re-plans only the areas whose numbers change.")
    st.setdefault("seen", [])
    st["seen"] += [fingerprint(b) for b in blocks]
    first = len(st["messages"]) + 1
    msgs = reader.read(blocks, first, tr)
    old_plan = st["plan"]
    world, plan = st["world"], st["plan"]
    replanned, predicted = set(), set()
    for m in msgs:
        if m.get("status_hint") and not m["f"]:
            m["status"], m["reason"] = "not read", m["status_hint"]
            tr.note("reading", f"message #{m['id']}: {m['status_hint']}; plan unchanged (run again to retry)")
            st["seen"].remove(fingerprint(m["text"])) if fingerprint(m["text"]) in st["seen"] else None
            st["messages"].append(m)
            continue
        if not m.get("rel") and not m["f"]:
            m["status"], m["reason"] = "ignored", "no planning fact"
            tr.note("reading", f"message #{m['id']} ignored: no planning fact; plan unchanged")
            st["messages"].append(m)
            continue
        new_world, problems, areas = F.apply_message(world, m, tr, strict=True)
        predicted |= areas
        m["areas"] = sorted(areas)
        tr.note("reading", f"message #{m['id']} affects areas: {', '.join(sorted(areas)) or 'nothing'} "
                "(these will be re-validated by code)")
        if problems:
            # also show what would break if the message were accepted anyway (trial copy only)
            trial = P.build(new_world)
            if not trial["valid"]:
                problems.append(("R-VALID", "and even if accepted, the plan would break -> " + " | ".join(failed(trial))))
            for rule, why in problems:
                tr.reject(m["id"], rule, why)
            tr.note("budget", "plan kept unchanged (still valid)")
            why = " ; ".join(f"{r}: {y}" for r, y in problems)
            m["status"], m["reason"] = "rejected", why
            st["rejected"].append({"msg": m["id"], "rule": "+".join(dict.fromkeys(r for r, _ in problems)),
                                   "reason": why, "text": m["text"]})
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
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    path = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else None
    os.chdir(os.path.dirname(os.path.abspath(__file__)))     # state/, out/, messages.txt live next to main.py
    if path:
        files = [path]
    else:
        # messages.txt plus any .txt dropped in inbox/, oldest first. Each file is processed on its own,
        # and only messages never seen before count, so re-running never repeats work.
        files = [INBOX] if os.path.exists(INBOX) else []
        if os.path.isdir(INBOX_DIR):
            files += [os.path.join(INBOX_DIR, f) for f in os.listdir(INBOX_DIR) if f.lower().endswith(".txt")]
        files.sort(key=os.path.getmtime)
    if not files:
        print(f"No input. Put the pack (or a new message) in {INBOX}, or drop a .txt file in {INBOX_DIR}/, "
              "then run: python main.py")
        sys.exit(1)
    seen = set((load_state() or {}).get("seen", []))
    todo = []
    for f in files:
        with open(f, encoding="utf-8-sig") as fh:
            raw = fh.read()
        if path or any(fingerprint(b) not in seen for b in reader.split_messages(raw)):
            todo.append((f, raw))
            seen |= {fingerprint(b) for b in reader.split_messages(raw)}
    if not todo:
        print("No new messages in messages.txt or inbox/ (all processed before). Current plan:")
        st = load_state()
        if st:
            report.print_plan(st)
        return
    for f, raw in todo:
        print(f"\n>>> reading {f}")
        if process(raw, os.path.basename(f)) is None:
            sys.exit(2)


def process(raw, src_name):
    """Shared by the CLI and the web UI: decide full run vs update, run it, save every output."""
    st = load_state()
    blocks = reader.split_messages(raw)
    if not blocks:
        print("Input file is empty.")
        return st
    seen = set((st or {}).get("seen", []))
    new = [b for b in blocks if fingerprint(b) not in seen]
    try:
        if st is None or (len(new) == len(blocks) and len(blocks) >= PACK_MIN):
            if st is not None:
                print(f"({len(blocks)} unseen messages -> a new pack; starting a fresh plan)")
            st = full_run(blocks, src_name)
        elif not new:
            print("No new messages in the file (all were processed before). Plan unchanged.")
        else:
            print(f"({len(new)} new message(s), {len(blocks) - len(new)} already processed -> UPDATE)")
            st = update_run(st, new, src_name)
    except LLMError as e:
        print(f"MODEL ERROR: {e}\nPlan not changed.")
        return None
    save_state(st)
    os.makedirs(OUT, exist_ok=True)
    report.print_plan(st)
    report.write_files(st, OUT)
    report.write_json(st, OUT)
    ui.write(st, os.path.join(OUT, "index.html"))
    print(f"\nSaved: {OUT}/final_plan.json  {OUT}/execution_trace.json  {OUT}/rejected_messages.json  "
          f"{OUT}/final_report.txt  UI: {OUT}/index.html (or: python server.py)")
    return st


if __name__ == "__main__":
    main()
