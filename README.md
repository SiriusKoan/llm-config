# LLM Config

Collection of LLM resources, skills, agents, and tools.

## Submodules

- `academic-research-skills`
- `anthropics-skills`
- `awesome-codex-subagents`
- `caveman`
- `everything-claude-code`
- `superpowers`

## Setup

```bash
git clone https://github.com/siriuskoan/llm-config.git
cd llm-config
git submodule update --init --recursive
```

## CLI Configuration

```bash
# Claude (~/.claude)
ln -s $(pwd)/cli/claude/{settings.json,agents,skills,hooks} ~/.claude/

# OpenCode (~/.config/opencode)
ln -s $(pwd)/cli/opencode/opencode.json ~/.config/opencode/config.json
ln -s $(pwd)/cli/opencode/{agent,skill} ~/.config/opencode/

# Codex (~/.codex)
ln -s $(pwd)/cli/codex/{agents,hooks} ~/.codex/
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
