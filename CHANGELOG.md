# Changelog

All notable changes to this project are documented in this file.

## 2026-03-11

### Added

- Automation trigger APIs:
  - `POST /api/automation/triggers/agent`
  - `GET /api/automation/triggers/runs`
  - `GET /api/automation/triggers/runs/{run_id}`
- Token-based automation ingress auth:
  - `RESEARCHCLAW_AUTOMATION_TOKEN` (env)
  - `config.automation.token` (fallback)
- In-memory automation run history store with bounded retention and status transitions (`queued`, `running`, `succeeded`, `failed`).
- Multi-channel delivery options for automation runs:
  - explicit `dispatches`
  - `fanout_channels` (`["*"]` supported for all active channels)

### Changed

- Control-plane observability:
  - `GET /api/control/status` now returns `runtime.runner`, `runtime.channels`, `runtime.cron`, and `runtime.automation` snapshots.
  - Added `GET /api/control/channels/runtime` for queue/worker-level channel runtime stats.
  - Added `GET /api/control/automation/runs` for recent automation run records.
- Channel manager now exposes queue/pending/in-progress/worker runtime metrics via `get_runtime_stats()`.
- Cron manager now exposes runtime counters via `get_runtime_stats()`.
- Console Status page now surfaces:
  - registered channel count
  - queued message backlog
  - in-progress channel keys
  - automation success/failure counters

### Tests

- Added `tests/test_automation_trigger.py`:
  - dispatch normalization/deduplication
  - fan-out expansion (`*` support)
  - fallback to `last_dispatch`
  - automation run store lifecycle

