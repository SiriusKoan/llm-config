---
name: orchestrating-work-in-tmux
description: Use when Codex needs to organize ongoing work in tmux so a human can monitor it, especially when switching between directories, projects, windows, panes, or remote hosts over SSH while keeping commands and output visible. Run important commands inside the tmux session so the session itself remains the visible execution surface rather than relying on a separate running-command tool.
---

# Orchestrating Work in Tmux

## Overview

Use this skill to make tmux the visible control surface for agent work. Build a session that separates roles clearly, move between local and remote contexts intentionally, and keep enough output on screen that a human can understand what the agent is doing without reconstructing hidden state.

Treat tmux as the primary execution environment for meaningful work. If a command matters for progress, debugging, monitoring, or handoff, run it inside a tmux pane so the command and its output remain visible in the session history.

## Workflow

1. Define the workspaces and commands that need to stay visible.
2. Create or attach a dedicated tmux session before starting important work.
3. Assign windows and panes by role, directory, or host.
4. Enter each context explicitly inside its pane.
5. Run important commands in tmux and keep monitor panes readable while work proceeds.
6. Report the session layout and current state.

## Define the Visible Work

Before creating panes, decide what the human should be able to watch.

Capture these choices:

- Contexts: local directories, repos, or remote hosts involved.
- Roles: editor, runner, logs, monitor, deploy, shell, or analysis.
- Important commands: builds, tests, servers, tails, deploys, SSH sessions, long-running diagnostics, or any step the human may need to inspect later.
- Concurrency: which tasks must remain visible at the same time.
- Persistence: whether the session should remain alive after the turn.

If the request is underspecified, prefer a small layout with clear labels over a dense one.

## Create the Session

Use a dedicated session name such as `orch-api-prod`, `orch-multi-repo`, or `orch-ssh-debug`. Reuse a session only when it is clearly the same ongoing task.

Preferred pattern:

- One session per task thread.
- One window per host or major role.
- One pane per concurrently observed process.

Use tmux tools in this order:

1. `create_session`
2. `create_window` for a new host, repo, or role
3. `split_pane` for simultaneous visibility inside one context
4. `execute_command` to change directory, connect over SSH, and run the important commands inside tmux
5. `capture_pane` to inspect state and summarize it

Do not use a separate running-command tool for work that should be observable in the session. Keep execution and monitoring in tmux unless there is a clear reason a command must stay outside it.

## Model the Layout Around Human Monitoring

Optimize for observability first.

### Single local workspace

Use one window when all work stays in one directory. Split into two panes only if the human benefits from seeing command output beside an interactive shell.

### Multiple directories or repos

Use separate windows when work spans different local directories. Treat each window as a stable home for one repo or one role so the human can switch contexts without guessing where state lives.

### Remote hosts over SSH

Use separate windows for different hosts. Enter the host in that window, keep the connection there, and avoid hopping one pane across multiple machines unless the task is trivial.

### Mixed control and observation

Use one pane to perform actions and another pane to tail logs, run `watch`, inspect process state, or capture diagnostics. Keep the monitor pane quiet enough that the human can read it.

## Enter Context Explicitly

Do not assume hidden shell state.

When changing context:

- Change to the intended directory before running project commands.
- Enter SSH explicitly in the pane or window meant for that host.
- Keep one context per pane whenever possible.
- If a pane changes roles, say so in the next status update.
- Start the meaningful command from that pane after the context is established, instead of launching it elsewhere.

The goal is that a human reading the pane history can tell where the agent is operating.

## Run Work Without Losing Legibility

Launch commands deliberately and preserve readable output.

Guidelines:

- Use `execute_command` for each state transition that matters and for the important commands themselves.
- Avoid stacking unrelated commands in a busy pane.
- Use `rawMode=true` only for interactive programs or TUI navigation.
- Poll with `capture_pane` so the human can be told what is on screen.
- If work is long-running, keep a nearby pane for logs or health checks.
- Reserve non-tmux command execution for lightweight inspection that does not need to remain visible or interactive.

Important commands usually belong in tmux:

- Starting dev servers, watchers, or background workers
- Running builds, test suites, migrations, or deploy commands the human may want to observe
- Opening SSH sessions and running remote operations
- Tailing logs, watching metrics, or following long-running diagnostics

Lightweight commands may stay outside tmux when visibility adds no value:

- Quick file discovery
- Brief reads of local files
- Small one-shot checks whose output is immediately summarized and not useful to monitor live

## Keep the Human in the Loop

Treat tmux as a shared cockpit, not a hidden backend.

Make the layout understandable:

- Keep pane purpose stable.
- Prefer additional windows over overpacked panes.
- Mention session, window, and pane roles in updates.
- Preserve long-running sessions unless cleanup is clearly safe.

Capture enough output to answer:

- What context is this pane in?
- What command is running?
- Is it idle, active, blocked, or failed?
- What should the human look at next?
- Which important commands were intentionally kept in tmux?

## Preserve Sessions by Default

Prefer leaving the session alive when:

- Work is still running.
- The human may inspect or take over.
- The panes contain useful remote or directory-local state.

Clean up only when the task is finished and the session no longer provides value.

## Reporting Pattern

When reporting back, include:

- Session name
- Window and pane roles
- Which directories or hosts each window represents
- Commands started or currently running, highlighting the important ones kept in tmux
- Key visible output from captures
- Whether the session remains available for monitoring

## Common Mistakes

- Treating tmux as an invisible executor instead of a human-visible workspace.
- Running important commands outside tmux and leaving the session without the real execution history.
- Mixing several directories or hosts in one pane with no clear boundary.
- Reusing one SSH pane for multiple machines and losing attribution.
- Starting long-running work without a monitor pane.
- Cleaning up the session before the human has finished observing it.
