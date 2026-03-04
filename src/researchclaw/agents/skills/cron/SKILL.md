# Cron – Scheduled Research Tasks

- name: cron
- description: Create and manage scheduled tasks that run automatically — periodic literature checks, data collection, report generation, and more.
- emoji: ⏰
- requires: []

## Core Commands

All cron management is done via the `researchclaw cron` CLI:

| Command | Description |
|---------|-------------|
| `researchclaw cron list` | List all scheduled tasks |
| `researchclaw cron get <id>` | Show task details |
| `researchclaw cron create ...` | Create a new scheduled task |
| `researchclaw cron delete <id>` | Delete a task |
| `researchclaw cron pause <id>` | Pause a task |
| `researchclaw cron resume <id>` | Resume a paused task |
| `researchclaw cron run <id>` | Trigger a task immediately |
| `researchclaw cron state <id>` | Show recent execution history |

## Task Types

### `text` — Send a fixed message on schedule
```bash
researchclaw cron create \
  --type text \
  --name "daily-reminder" \
  --cron "0 9 * * *" \
  --channel console \
  --text "Check for new papers on arxiv today."
```

### `agent` — Ask the agent a question on schedule
```bash
researchclaw cron create \
  --type agent \
  --name "weekly-arxiv-scan" \
  --cron "0 8 * * 1" \
  --channel console \
  --text "Search arxiv for papers on 'large language models' published this week and summarize the top 5."
```

## Research-Specific Use Cases

- **Daily arxiv scan**: Check for new papers in your field every morning
- **Weekly literature digest**: Generate a summary of recent publications
- **Data pipeline triggers**: Run data collection/analysis at scheduled intervals
- **Citation alerts**: Monitor citation counts for key papers
- **Conference deadline reminders**: Automated reminders for submission deadlines

## Cron Expression Reference

| Expression | Description |
|-----------|-------------|
| `0 9 * * *` | Daily at 9:00 AM |
| `0 8 * * 1` | Every Monday at 8:00 AM |
| `0 */6 * * *` | Every 6 hours |
| `0 0 1 * *` | First day of each month |
| `30 17 * * 5` | Every Friday at 5:30 PM |

## Supported Channels

Tasks can deliver results to any configured channel:
- `console` — Terminal / web console
- `telegram` — Telegram bot
- `discord` — Discord bot
- `dingtalk` — DingTalk bot
- `feishu` — Feishu/Lark bot
- `imessage` — iMessage (macOS)
- `qq` — QQ bot

## Rules

- Always confirm the cron expression with the user before creating
- Use descriptive task names
- For `agent` tasks, write clear and specific prompts
- Suggest appropriate scheduling frequency (don't over-poll)
