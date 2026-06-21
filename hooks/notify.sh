#!/usr/bin/env bash
#
# Unified Telegram notifier for coding agents. Agent name is $1 and selects
# how the rest of the input arrives:
#   claude : notify.sh claude                    (hook JSON on stdin)
#   codex  : notify = [".../notify.sh", "codex"]  (Codex appends JSON as $2)
#
# Credentials: ~/.claude/telegram.env (override with TELEGRAM_ENV_FILE):
#   TELEGRAM_BOT_TOKEN=...   TELEGRAM_CHAT_ID=...
# Missing file/values -> silent no-op.

set -uo pipefail

ENV_FILE="${TELEGRAM_ENV_FILE:-$HOME/.claude/telegram.env}"
[ -f "$ENV_FILE" ] || exit 0
# shellcheck disable=SC1090
. "$ENV_FILE"
[ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ] || exit 0

jqf() { printf '%s' "$1" | jq -r "$2 // empty" 2>/dev/null || true; }  # jqf <json> <filter>

label=""; event=""; title=""; cwd=""; message=""
case "${1:-}" in
  claude)
    label="Claude Code"; json="$(cat)"
    event="$(jqf "$json" .hook_event_name)"
    cwd="$(jqf "$json" .cwd)"
    message="$(jqf "$json" .message)"
    tp="$(jqf "$json" .transcript_path)"
    [ -f "$tp" ] && title="$(jq -r 'select(.type=="ai-title").aiTitle' "$tp" 2>/dev/null | tail -1)"
    ;;
  codex)
    label="Codex"; json="${2:-}"
    event="$(jqf "$json" .type)"
    cwd="$(jqf "$json" .cwd)"
    title="$(jqf "$json" '.["input-messages"][0]')"
    ;;
  *) exit 0 ;;
esac

case "$event" in
  Stop|agent-turn-complete)        text="✅ $label — session is done" ;;
  Notification|approval-requested) text="🔔 $label — needs your attention" ;;
  SessionEnd)                      text="👋 $label — session ended" ;;
  *)                               text="📣 $label — ${event:-event}" ;;
esac

title="${title//$'\n'/ }"
[ -n "$message" ]   && text+=$'\n'"$message"
[ -n "$title" ]     && text+=$'\n'"📌 ${title:0:120}"
[ -n "${cwd##*/}" ] && text+=$'\n'"📁 ${cwd##*/}"

curl -fsS --max-time 10 \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  --data-urlencode "text=${text}" >/dev/null 2>&1 || true
