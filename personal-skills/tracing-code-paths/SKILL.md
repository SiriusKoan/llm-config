---
name: tracing-code-paths
description: Use when a user describes a runtime scenario ("what happens when this request comes in", "trace this webhook", "how does this job actually run") and wants to know which code executes - locates the entrypoint from the scenario alone, walks the call chain one hop at a time anchored to file:line, and stops to ask the user at every branch the scenario does not determine. For large or unfamiliar codebases.
---

# Tracing Code Paths

Turn a scenario the user describes in prose into one concrete path through the code, from entrypoint to outcome, every step anchored to a line that was actually read.

The scenario is always underspecified. The code branches on things the user never mentioned. **Those branches belong to the user, not to the tracer** — the value of the trace is that it follows *their* case, and a fabricated premise produces a trace that is worthless while looking complete.

## Critical Guidelines

- You MUST fix the user's stated facts as premises before reading code, and MUST NOT add to them. A branch that turns on something unstated is a question, not a judgement call.
- You MUST ask at the fork, on reaching it — not as one framing question up front.
- You MUST confirm the entrypoint is reachable from a real process start before walking from it.
- You MUST anchor every step to a `file:line` that was opened. Never a step from memory or inference.
- You MUST stay on the trace. Noticing a bug is not a licence to review the codebase.

## How to Use

### 1. Fix the premises

Restate the scenario and list what the user actually said. That list is closed. Everything else is unknown, and every unknown is a future question. Read no code yet.

### 2. Find the entrypoint

Literal strings from the scenario survive into the code — start there.

| Scenario mentions | Grep for |
|---|---|
| a URL / route | the path literal, then whatever route table holds it |
| a CLI invocation | the subcommand string, the arg-parser setup |
| an event, webhook, or topic | the event name, then subscriber registration |
| scheduled or polled work | the loop, the scheduler registration |
| a message the user saw | the literal string |
| nothing quotable | the domain noun, then narrow by directory |

Then place it: what starts this process? A handler is not an entrypoint if nothing routes to it — walk out to `main` / the server bootstrap / the worker loop and confirm the path in. `references/entrypoints.md` holds the per-framework conventions.

State the entrypoint and how it was found before walking. If two plausible entrypoints exist, that is a fork — ask.

### 3. Walk one hop at a time

At each frame: read the function, find where control leaves. Record `file:line`, what it does, what it decides.

Follow the scenario's data, not the plumbing. Descend where the payload goes; do not descend into logging, config getters, or leaf utilities.

**Where traces break** — dynamic dispatch hides the next hop. Resolve by finding the registration, never by guessing:

- interface / abstract method → find implementations, select by the premise that picks one
- decorator / middleware chain → find where the chain is assembled, and in what order
- event bus / queue / signal → grep the event name for publishers *and* subscribers
- DI container / registry / plugin loader → find the binding
- reflection or string-built dispatch → grep the string fragments that compose the name

If which implementation runs cannot be resolved from the premises, that is a fork — ask.

### 4. Ask at forks

A fork is a branch whose condition depends on a fact absent from the premises.

Ask with AskUserQuestion. Options are the actual branches in the code, each stating what happens if taken. Batch independent forks reached together (max 4); ask sequentially when one fork decides whether the next is reached.

**Not a fork — do not ask:**

- The premises already decide it → state the decision and its premise, keep walking.
- A guard or error path that exits the scenario → one clause ("bails here if X"), stay on the path.
- Branches that reconverge without affecting the outcome → ignore.

Spend the premises before spending a question. Two ways they pay:

- **The outcome is a premise too.** If the user said the PR got opened, every branch that cannot open a PR is eliminated — no question needed. Work backwards from the stated result.
- **The repo holds facts the user never stated.** Config, manifests, and fixtures are read, not assumed: if `repos.yaml` pins one agent, that branch is decided. Cite the line like any other step.

Never resolve a fork by picking the common case, the first branch, or the one already read.

### 5. Stop

Stop when the scenario's outcome occurs (response returned, row written, PR opened) or the path leaves the codebase (external call, DB, another service). Name the boundary; do not trail off.

### 6. Deliver

A numbered chain — each step one or two sentences carrying its `file:line`. Then the forks and how the user resolved them. If the user asked a question the chain answers only implicitly ("how does it pick the agent?"), answer it directly in a few lines at the end.

That is the whole deliverable. Anything else noticed along the way — bugs, stale docs, races — is at most one line, offered as a follow-up.

## Example

Scenario: *"a user uploads an avatar and it ends up on the CDN — trace it."*

Premises: an upload happens; it reaches a CDN. **Not** given: authenticated or not, image format, sync or queued.

Walking hits `if user.plan == "free"` at `api/upload.py:64`:

> **Free plan or paid?** — `api/upload.py:64`
> - **Free** → 2 MB cap, resized to 256px inline, `storage/local.py:30`
> - **Paid** → 20 MB cap, queued to the transcoder, `tasks/media.py:12`
>
> (asked, because nothing in the scenario says which)

Deliverable shape:

```
1. **Request lands** — `api/routes.py:88` — POST /v1/avatar, bound in the router at `api/app.py:41`.
2. **Auth middleware** — `middleware/auth.py:23` — rejects without a session; your case is signed in (you said so).
3. **Size check** — `api/upload.py:64` — paid plan (你選的), so the 20 MB cap applies.
...
7. **CDN publish** — `storage/cdn.py:57` — PUT to S3; the trace leaves the codebase here.

Forks you decided: paid plan · original format kept · async transcode
```

## Troubleshooting

| Rationalization | Reality |
|---|---|
| "The scenario obviously means the normal case" | "Obviously" is a premise the user did not give. That *is* the fork. Ask. |
| "I'll note the assumption and continue" | An assumption noted mid-prose is still a fabricated trace. This skill exists to ask. |
| "I'll trace both branches instead of asking" | Two traces are not a trace. The reader cannot tell which is theirs. |
| "I'll ask everything up front, then work uninterrupted" | At the fork the real options are visible; up front they are guesses. Ask late, ask concretely. |
| "I found a bug while tracing" | One line at the end. Offer to look properly afterwards. |
| "This function has four branches, I'll list them all" | List the one taken. The rest is noise dressed as thoroughness. |
| "I can't find the implementation, I'll assume the obvious one" | Unresolvable dispatch is a fork. Ask which one the scenario uses. |

## Red Flags

- Prose containing "presumably", "typically", "assuming a normal ..."
- A branch resolved by a fact the user never stated
- A step with no `file:line`
- A "notes / observations / other issues" section that grew past one line
- Arriving at the deliverable having asked zero questions

## Resources

- `references/entrypoints.md` — where routes, middleware, and process starts live in common frameworks (Django, FastAPI, Flask, Express, NestJS, Spring, Rails, Go, Laravel, ASP.NET) and in non-HTTP entrypoints (Celery, Sidekiq, Kafka, Lambda, gRPC, CLI).
