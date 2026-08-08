# Agent Rules

Always enable `i-have-adhd:i-have-adhd` for every task: coding, review, surveying, and research.

All source code and code comments must be written in English.

## Plan

- Before any plan, ask whether to use a grill-series skill; user may decline, including for simple tasks.
- If yes, use `grill-me` and run `/grilling` to confirm goal, non-goals, requirements, constraints, acceptance criteria, affected files, and verification method.
- Do not modify code until the spec is confirmed.

## Coding

- Always enable `ponytail:ponytail` when writing code.
- Before implementation, ask whether to launch a subagent; user may decline, including for simple tasks.
- TDD: Red → Green → Refactor — failing test, minimal implementation, refactor.
- Test public interfaces and observable behavior, not implementation details.
- After implementation, use code-review when applicable.

## Research and Discussion

- Prefer `academic-research-skills` for research when available.
- Define question and scope before searching; prefer primary sources, systematic reviews, official statistics, authoritative datasets.
- Treat user claims as hypotheses; search supporting and falsifying literature/data.
- Evaluate counterevidence fairly; do not oppose without evidence.
- Cite every externally verifiable claim; never invent citations, sources, quotations, or data.
- Distinguish sourced facts, inferences, and uncertainties.

## Documentation

- Documentation may use Traditional Chinese, but all code and code comments must remain in English.

## Completion

- Before claiming completion, use `verification-before-completion`; run relevant tests, checks, and quality validation.
