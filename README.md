# Hackathon Planner: "read with a model, decide with code"

## One command, every time

```
python main.py
```

It reads **`messages.txt`** (next to `main.py`; git-ignored, so `git status` stays clean).

| What is in `messages.txt` | What happens |
|---|---|
| A whole pack of messages, none seen before (4 or more) | **Full run**: a fresh plan. Limit 120 s. |
| Any message(s) not processed before (replace the file with the new message, or append it) | **Update**: only the new message(s) are read. Limit 60 s and at most 5 model calls. |
| Nothing new | Prints the current plan; no model call. |

Setup: `pip install requests`, then copy `.env.example` to `.env`. Any OpenAI-compatible endpoint works
(`BASE_URL`, `API_KEY`, `MODEL_NAME`; local Ollama, Groq, OpenAI ...).

**Three ways to give it messages** (all run the same pipeline, and nothing is ever processed twice):
1. Paste into `messages.txt`, then run `python main.py`.
2. Drop any `.txt` file into the `inbox/` folder, then run `python main.py`. Every file with unseen messages is processed, oldest first.
3. Web UI (`python server.py`): the "+ New message" tab, where you type a message or upload/drag a `.txt` file. The file is saved into `inbox/` and processed immediately.

**Languages:** messages may be in English or Roman Urdu (e.g. "students ki tadaad ab 165 hai", "Rs 950 fi kas, sada box Rs 600", "zyada se zyada 3 teams"). The dashboard has an **English / Roman Urdu** button (top right) that switches the interface text, check names and rejection explanations. The trace stays exactly as printed in the terminal.

Outputs (in `out/`): `final_plan.json`, `execution_trace.json`, `rejected_messages.json`,
`final_report.txt` (plan plus full printed trace, ready to upload) and `index.html` (dashboard).
Web UI with a "New message" box: `python server.py`, then open http://localhost:8000.

## Test-day procedure
1. Paste the unseen pack into `messages.txt` and run `python main.py`.
2. For each new message: replace the contents of `messages.txt` with that message and run `python main.py`.
3. **Prediction slip:** only the **reading** area makes model calls, one call per new message.
   venue, schedule, food, judging and budget make **0** model calls (they are code).
   After reading, the trace lists which areas the message affects; code re-plans only those.
4. Upload `out/final_report.txt` (or the JSON files).

## How it works (what each part is for, and what breaks without it)

```
messages.txt -> split (code) -> header: sender, date, role (code)
             -> tag every number (code) -> rules.py labels obvious numbers (code)
             -> model labels the rest  [area tag: reading, 1 call per message]
             -> fact store: newest wins, authority checks (code)
             -> planner: venue / schedule / food / judging / budget (code)
             -> validator: the 6 checks (code) -> accept, or reject with rule + reason
             -> trace + JSON files + dashboard
```

| Part | File | What it does | What breaks without it |
|---|---|---|---|
| Splitter + header reader | `planner/reader.py` | Splits the file into messages, keeping the text exactly. Code reads each sender, date and role (dean = authority, caterer, finance ...) from the header | Dates and senders guessed by a model are wrong, so "newest wins" breaks |
| Number tagger | `planner/reader.py:tag` | Code finds every number and tags it `150(#2)`. **Values always come from the text, never from the model** | A model could invent or mistype a figure |
| Code-first labeller | `planner/rules.py` | General wording patterns ("150 students", "seats 250", "Rs 850 per head", "teams of 4", "at most 3 teams") label most numbers with no model. Also finds "venue must have X", "Hall X has Y" and "X is not available" | A tiny model mislabels obvious numbers |
| Model (reading only) | `planner/llm.py` | Labels whatever code could not. One short call per message, run in parallel | Unusual wording and new kinds of constraint would be missed |
| Fact store | `planner/facts.py` | Merges facts with provenance. **R-STALE**: an older message never overrides a newer one (out-of-date prices). **R-AUTH**: only someone with authority can change core settings | Old prices are used; a student could change the budget |
| Planner | `planner/plan.py:build` | Pure arithmetic. People = students + judges needed + staff + extra. Judges needed = ceil(teams x judges per team / max teams per judge). Cheapest venue that fits and meets every rule. Food tier preference. Schedule fills the exact duration | The model would do the maths, costing tokens and getting numbers wrong |
| Validator | `planner/plan.py:validate` | The 6 graded checks, plus **R-COVER** (a promised quantity such as 100 boxes is below what is needed) | Nothing would stop a bad message from breaking the plan |
| Update gate | `main.py:update_run` | Applies a new message to a **copy** of the state. If any rule or check fails, the message is rejected, the old valid plan is kept, and the reason is printed | One wrong message would break the plan |
| Trace | `planner/trace.py` | Each model call: number, model, area tag, input, output, tokens **as the API reported them**, seconds. Code decisions are printed as `[CODE · area]` | No proof of tokens or reasoning |
| Policies | `policies.json` | **Our** choices, not facts: default start time, lunch length, food-tier preference, who may approve extra spending | Planning defaults would be hidden in code |
| UI | `planner/ui.py`, `server.py` | Plan, constraints, inbox with status, rejected messages with reasons, trace, tokens per run, predicted vs re-planned areas, new-message box | Judges can't see the plan quickly |

## Rejection rules (printed in the trace as `[REJECTED · message #n] rule ...`)
* **R-COVER**: a promised quantity (food boxes, seats, judges) is lower than the plan needs.
* **R-AUTH**: the sender has no authority over the setting they are changing (e.g. a student society setting the budget).
* **R-STALE**: the message is dated earlier than the fact it tries to replace.
* **R-VALID**: accepting it would make one of the 6 checks fail (too few judges, over budget, venue too small, schedule doesn't fit).
* **R-CONFLICT**: the message contradicts an established fact. Example: someone who is not the venue says "Hall B has 150 seats" when the venue itself said 200.

A rejection lists **every** rule it breaks, plus what would break if it were accepted anyway. Example:
"Hamain Hall B pay shift karna chahiyay us main 150 seats hain" → R-CONFLICT (venue said 200) + R-AUTH (unknown sender can't choose the venue) + R-VALID (Hall B: 150 < 177 needed). The plan stays on Hall A.
Venue decisions ("move the event to Hall C", "Hall C book kar lein") are applied only from someone with authority, and only if the chosen venue passes every check.
A message with no sender line gets **no authority** in an update: the model's guess of who sent it is never trusted.

Requests ("Can we get a DJ?") are paid for only if someone with budget authority asked; otherwise they are listed as declined, with the reason.

## Token efficiency
Only reading uses a model, and most numbers are labelled by code. A full run of the sample pack is about 5.4k tokens across 8 calls; an update is about 630 tokens in 1 call.
The default model is `qwen2.5` running locally (on the small-model list, since it runs on our laptop).

## Tests
`samples/` holds the brief's sample pack and its two practice messages. `tests/pack2/` holds our own unseen-style pack: new senders, Roman Urdu, a wheelchair-access rule, volunteers, a 9:00 start, a 5-hour event. Its four updates are 2 valid, 1 with too few judges and 1 with no authority.

```
python main.py samples/sample_pack.txt    # (optional path argument for testing)
python main.py samples/change_printing.txt
python main.py samples/wrong_caterer.txt
```
