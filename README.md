# Hackathon Planner: "read with a model, decide with code"

One command, every time:

```
python run.py <messages.txt>
```

* If there is no saved plan yet, or the file holds a whole pack (4 or more messages), it plans from scratch.
* Otherwise it treats the file as new message(s) and **updates** the saved plan.
* The trace prints to the terminal. The files `out/plan.txt`, `out/trace.txt` and `out/final_report.txt` are written, and `out/index.html` is the UI. Open it in any browser; it refreshes itself.

Setup: `pip install requests`, then copy `.env.example` to `.env` and add your key. Any OpenAI-compatible endpoint works (Groq, Ollama, OpenRouter, ...).

## Architecture (and what breaks without each part)

| Part | File | What it does | Without it |
|---|---|---|---|
| Reader (the **only** model call) | `planner/reader.py` | Turns raw English / Roman Urdu messages into typed facts (`set`, `venue`, `food`, `spent`, `req`, `need`, `qty`, `note`), with sender role and date | Code cannot understand free text |
| Fact store | `planner/facts.py` | Merges facts and remembers which message each came from. The newest date wins (**out-of-date** messages are superseded). **R-STALE**: an older message can't override. **R-AUTH**: only someone with authority can change core settings (budget, headcount, hours) | Old prices get used, and a student could raise the budget |
| Planner | `planner/plan.py` | Pure arithmetic. People = students + judges needed + staff + extras. Judges = ceil(teams × judges per team ÷ max teams per judge). Venue = cheapest one that fits and meets every rule. An **optimizer** searches venue × food tier × optional requests and keeps essentials first. The schedule fills the exact duration | The LLM would do the maths, which costs tokens and gets numbers wrong |
| Validator | `planner/plan.py:validate` | Runs the 6 graded checks: figures, budget, venue fits, schedule valid, enough judges, all areas covered. It also checks quantity promises (**R-COVER**) | Nothing would stop an invalid plan or a wrong message |
| Update gate | `run.py:update_run` | Applies a new message to a copy of the plan. If any rule fails, it **rejects the message, keeps the old valid plan and prints why**. Otherwise it re-plans only the areas whose numbers changed | One bad message would break the plan |
| Trace | `planner/trace.py` | For every model call: number, model, area, input, output, and tokens as reported by the API. Code decisions are logged as `[CODE · area]` with 0 tokens | No proof of tokens or reasoning |
| UI | `planner/ui.py` | A single self-contained HTML file with tabs for Plan, Inbox, Rejected, Trace, and Runs & tokens | Judges can't see the plan quickly |
| Policies | `policies.json` | **Our** planning choices: start time, lunch length, food-tier preference. These are not facts from messages | Planning defaults would be hidden in code |

## Why this design wins on the scoring
* **Tokens**: one model call per full run and one per update. Arithmetic is free.
* **Small model bonus**: extraction is the only model task, so an 8B model or smaller works.
* **Predicting a change**: only the `reading` area ever makes a model call. Code re-plans the affected areas, and the trace shows which.
* **Catching the wrong message**: named rules (R-COVER, R-AUTH, R-STALE, R-VALID) each print a reason.
* **New kinds of constraint**: the generic `need` facts (break, require, min_capacity, max_cost, extra_people, surcharge, forbid, fixed) are applied by code. Anything else becomes a `note` that is shown in the plan.

## Rules for rejecting a message
* **R-COVER**: a promised quantity (food boxes, seats, judges) is lower than what the plan needs.
* **R-AUTH**: the sender has no authority over the thing they are changing.
* **R-STALE**: the message is dated earlier than the fact it tries to replace.
* **R-VALID**: accepting the message would make any of the 6 checks fail.
