"""Human-readable plan for the terminal and the files we upload (plan + full trace)."""
import os


def plan_text(st):
    p = st["plan"]
    hc, b, j, s = p["headcount"], p["budget"], p["judging"], p["schedule"]
    L = []
    L.append("=" * 78)
    L.append(f"EVENT PLAN   status: {'VALID - all 6 checks pass' if p['valid'] else 'CHECKS FAILING'}")
    L.append("=" * 78)
    L.append(f"People: {hc['students']} students in {hc['teams']} teams of {hc['team_size']}, "
             f"+ {j['judges_used']} judges + {hc['staff']} staff" + (f" + {hc['extra']} extra" if hc["extra"] else "")
             + f" = {p['people']} to seat & feed")
    L.append("")
    v = p["venue"]
    L.append("VENUE")
    if v:
        L.append(f"  {v['name']}: {v['cap']} seats, Rs {v['cost']:,}" + (f"  [{', '.join(v['feat'])}]" if v["feat"] else "")
                 + f"   (source: msg #{v['src']})")
    for r in p["venue_rejected"]:
        L.append(f"  x {r}")
    L.append("")
    L.append(f"SCHEDULE  {s['start']} - {s['end']} ({s['duration_min']} min)")
    for x in s["slots"]:
        L.append(f"  {x['start']:>8} - {x['end']:>8}  {x['what']} ({x['min']} min)")
    L.append("")
    f = p["food"]
    L.append("FOOD")
    if f:
        L.append(f"  {f['boxes']} x {f['name']} ({f['tier']}) @ Rs {f['pph']:,} = Rs {f['cost']:,}   (source: msg #{f['src']})")
        for a in f["alternatives"]:
            L.append(f"  alt: {a['tier']} @ Rs {a['pph']:,} = Rs {a['cost']:,}")
    L.append("")
    L.append("JUDGING")
    L.append(f"  {j['judges_used']} of {j['judges_confirmed']} confirmed judges, {j['teams_per_judge']} teams each "
             f"x {j['min_per_team']} min = {j['block_min']} min block; {j['reserve_judges']} on standby")
    L.append("")
    L.append("BUDGET")
    for ln in b["lines"]:
        L.append(f"  Rs {ln['amt']:>9,}  {ln['item']}" + (f"   (msg #{ln['src']})" if ln.get("src") else ""))
    L.append(f"  Rs {b['total']:>9,}  TOTAL of Rs {b['limit']:,}  -> Rs {b['left']:,} left" if b["limit"] is not None
             else f"  Rs {b['total']:,} TOTAL (no budget given)")
    for d in b["declined"]:
        L.append(f"  declined: {d['item']} Rs {d['amt']:,} - {d['why']}")
    if p["notes"]:
        L.append("")
        L.append("OTHER CONSTRAINTS NOTED")
        for n in p["notes"]:
            L.append(f"  [{n['area']}] {n['text']} (msg #{n['msg']})")
    L.append("")
    L.append("CHECKS")
    for c in p["checks"]:
        L.append(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['check']}: {c['why']}")
    if st["rejected"]:
        L.append("")
        L.append("REJECTED MESSAGES")
        for r in st["rejected"]:
            L.append(f"  #{r['msg']} [{r['rule']}] {r['reason']}")
            L.append(f"      \"{r['text'][:140]}\"")
    return "\n".join(L)


def print_plan(st):
    try:
        print("\n" + plan_text(st))
    except UnicodeEncodeError:
        print(plan_text(st).encode("ascii", "replace").decode())


def write_files(st, out):
    pt = plan_text(st)
    tt = "\n".join(st["trace_lines"])
    with open(os.path.join(out, "plan.txt"), "w", encoding="utf-8") as fh:
        fh.write(pt + "\n")
    with open(os.path.join(out, "trace.txt"), "w", encoding="utf-8") as fh:
        fh.write(tt + "\n")
    with open(os.path.join(out, "final_report.txt"), "w", encoding="utf-8") as fh:
        fh.write(pt + "\n\n\nFULL TRACE (all runs)\n" + tt + "\n")
