"""Trace: every model call numbered with model, area tag, input, output and the
token counts the API reported. Code decisions are logged too (marked CODE, 0 tokens)
so a judge can see *why* the plan looks the way it does.
"""
import sys

from . import llm

AREAS = {"reading", "venue", "schedule", "food", "judging", "budget"}


class Tracer:
    def __init__(self, run_label, start_call_no=1):
        self.run_label = run_label
        self.events = []          # structured, for UI + state
        self.calls = 0
        self.next_no = start_call_no
        self.tokens = {"prompt": 0, "completion": 0, "total": 0}
        self.lines = []

    def _out(self, s=""):
        self.lines.append(s)
        try:
            print(s)
        except UnicodeEncodeError:
            print(s.encode("ascii", "replace").decode())
        sys.stdout.flush()

    def header(self):
        self._out("=" * 78)
        self._out(f"TRACE  {self.run_label}   model endpoint: {llm.BASE_URL}")
        self._out("=" * 78)

    def call(self, area, system, user):
        assert area in AREAS
        no = self.next_no
        self.next_no += 1
        text, usage, model, secs = llm.chat(system, user)
        self.calls += 1
        for k in self.tokens:
            self.tokens[k] += usage.get(k) or 0
        self._out(f"\n--- MODEL CALL #{no} | model={model} | area={area} | {secs}s ---")
        self._out("INPUT (system):")
        self._out(system.strip())
        self._out("INPUT (user):")
        self._out(user.strip())
        self._out("OUTPUT:")
        self._out(text.strip())
        self._out(f"TOKENS (reported by model): prompt={usage.get('prompt')} "
                  f"completion={usage.get('completion')} total={usage.get('total')}")
        self.events.append({"kind": "call", "no": no, "model": model, "area": area,
                            "input": system.strip() + "\n\n" + user.strip(),
                            "output": text.strip(), "usage": usage, "secs": secs})
        return text

    def note(self, area, msg):
        self._out(f"[CODE · {area}] {msg}")
        self.events.append({"kind": "code", "area": area, "msg": msg})

    def reject(self, msg_id, rule, reason):
        self._out(f"[REJECTED · message #{msg_id}] rule {rule}: {reason}")
        self.events.append({"kind": "reject", "msg": msg_id, "rule": rule, "reason": reason})

    def footer(self, cumulative):
        self._out("")
        self._out("-" * 78)
        self._out(f"MODEL CALLS THIS RUN: {self.calls}")
        self._out(f"TOTAL TOKENS THIS RUN: prompt={self.tokens['prompt']} "
                  f"completion={self.tokens['completion']} total={self.tokens['total']}")
        self._out(f"TOTAL TOKENS ALL RUNS: {cumulative}")
        self._out("-" * 78)
