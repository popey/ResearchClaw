# ResearchClaw Console

Minimal web console for ResearchClaw, built with React + Vite.

## Features

- CoPaw-like sidebar console layout (Chat / Papers / Status / Environments / MCP / Control)
- Chat with `Scholar` via `/api/agent/chat`
- Search papers via `/api/papers/search`
- Runtime control via `/api/control/*` (status, cron-jobs, heartbeat)
- Environment management via `/api/envs`
- MCP client management via `/api/mcp`

## Development

```bash
cd console
npm install
npm run dev
```

Then open the Vite URL (usually http://localhost:5173).

## Production Build

```bash
cd console
npm install
npm run build
```

Build output is written to `console/dist`.

The backend app (`src/researchclaw/app/_app.py`) automatically serves this folder when available.
