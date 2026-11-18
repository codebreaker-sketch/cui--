"""Trace: every model call numbered with model, area tag, input, output and the
token counts the API reported. Code decisions are logged too (marked CODE, 0 tokens)
so a judge can see *why* the plan looks the way it does.
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from . import llm

AREAS = {"reading", "venue", "schedule", "food", "judging", "budget"}


class Tracer:
    def __init__(self, run_label, start_call_no=1, limit_s=None, max_calls=None):
        self.run_label = run_label
        self.t0 = time.time()
        self.deadline = self.t0 + limit_s - 3 if limit_s else None   # 3 s kept for planning + saving
        self.limit_s, self.max_calls = limit_s, max_calls
        self.events = []          # structured, for UI + state
        self.calls = 0
        self.next_no = start_call_no
        self.tokens = {"prompt": 0, "completion": 0, "total": 0}
        self.lines = []
        self._shown = set()

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

    def call_many(self, area, system, users):
        """Runs several calls in parallel, then logs them in order. Returns texts (None = failed)."""
        assert area in AREAS
        if self.max_calls is not None and len(users) > self.max_calls - self.calls:
            raise llm.LLMError(f"would need {len(users)} model calls, limit is {self.max_calls}")
        workers = int(llm.os.environ.get("LLM_PARALLEL", "4"))

        def one(u):
            try:
                return llm.chat(system, u, deadline=self.deadline)
            except llm.LLMError as e:
                return e
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            results = list(ex.map(one, users))
        out = []
        for u, r in zip(users, results):
            if isinstance(r, Exception):
                self._out(f"\n--- MODEL CALL FAILED | area={area} | {r} ---")
                self.events.append({"kind": "code", "area": area, "msg": f"model call failed: {r}"})
                out.append(None)
            else:
                out.append(self._log(area, system, u, *r))
        return out

    def call(self, area, system, user):
        assert area in AREAS
        if self.max_calls is not None and self.calls >= self.max_calls:
            raise llm.LLMError(f"model-call limit ({self.max_calls}) reached")
        return self._log(area, system, user, *llm.chat(system, user, deadline=self.deadline))

    def _log(self, area, system, user, text, usage, model, secs):
        no = self.next_no
        self.next_no += 1
        self.calls += 1
        for k in self.tokens:
            self.tokens[k] += usage.get(k) or 0
        self._out(f"\n--- MODEL CALL #{no} | model={model} | area={area} | {secs}s ---")
        if system not in self._shown:
            self._shown.add(system)
            self._out("INPUT (system prompt, printed in full once per run; later calls reuse it word for word):")
            self._out(system.strip())
        else:
            self._out(f"INPUT (system): same reader prompt as above ({len(system)} chars)")
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
        self._out(f"TIME THIS RUN: {round(time.time() - self.t0, 1)} s"
                  + (f" (limit {self.limit_s} s)" if self.limit_s else ""))
        self._out(f"TOTAL TOKENS THIS RUN: prompt={self.tokens['prompt']} "
                  f"completion={self.tokens['completion']} total={self.tokens['total']}")
        self._out(f"TOTAL TOKENS ALL RUNS: {cumulative}")
        self._out("-" * 78)
