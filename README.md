# LLM Config

Collection of LLM resources, skills, and tools.

## Skill Sources

Submodules, plus one directory of hand-written skills:

- `academic-research-skills`
- `andrej-karpathy-skills`
- `caveman`
- `everything-claude-code`
- `book-to-skill`
- `localization-tw`
- `i-have-adhd`
- `ponytail`
- `superpowers`
- `personal-skills` — not a submodule; own skills live here

## Setup

```bash
git clone https://github.com/siriuskoan/llm-config.git
cd llm-config
git submodule update --init --recursive
```

## Shared Agent Instructions

Install shared `AGENTS.md` as Codex global instructions:

```bash
ln -s "$(pwd)/AGENTS.md" ~/.codex/AGENTS.md
```

## Selecting Skills

`skills/` is a flat directory of symlinks into the sources above, and is what every
CLI's skill directory points at. Pick which ones are linked:

```bash
uv run scripts/skills.py            # keys are listed on screen
uv run scripts/skills.py --dry-run  # show the diff, change nothing
```

It edits `skills/` in place — review with `git status` and commit. Skills of your own
go in `personal-skills/<name>/SKILL.md`.

## CLI Configuration

```bash
# Claude (~/.claude)
ln -s $(pwd)/cli/claude/{settings.json,skills,hooks} ~/.claude/

# OpenCode (~/.config/opencode)
ln -s $(pwd)/cli/opencode/opencode.json ~/.config/opencode/config.json
ln -s $(pwd)/cli/opencode/skill ~/.config/opencode/

# Codex (~/.codex)
ln -s $(pwd)/cli/codex/hooks ~/.codex/
```

## Notifications (Telegram)

`hooks/notify.sh <agent>` pings Telegram when an agent finishes or needs you.

1. **Creds** (untracked) — `~/.claude/telegram.env`, `chmod 600`:

   ```
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_CHAT_ID=...
   ```

2. **Claude** — already in `cli/claude/settings.json` (`Stop` + `Notification`).
3. **Codex** — add to `~/.codex/config.toml` (not repo-tracked; Codex auto-writes trust entries there). Absolute path, before any `[table]`:

   ```toml
   notify = ["/home/<you>/.codex/hooks/notify.sh", "codex"]
   ```

## Update

```bash
git submodule update --remote --recursive
```
