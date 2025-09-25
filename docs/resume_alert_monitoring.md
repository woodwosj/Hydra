# Resume Alert Monitoring Playbook

## Overview
Hydra emits `resume_alert` events whenever automatic Codex session resume attempts exceed the configured failure threshold (`HYDRA_RESUME_ALERT_THRESHOLD`, default 3). This document outlines how to surface and forward those alerts for operational monitoring.

## Quick Commands

### 1. Inspect latest alerts (CLI)
```bash
PYTHONPATH=src python scripts/hydra_diag.py alerts --limit 5
```

### 2. Filter by task
```bash
PYTHONPATH=src python scripts/hydra_diag.py alerts --task-id task-123 --limit 10
```

### 3. Forward alerts to monitoring sink
```bash
PYTHONPATH=src python scripts/hydra_alert_forwarder.py \
  --format text \
  --limit 10 \
  --output /var/log/hydra/resume_alerts.log
```

Combine the forwarder with shell pipelines to send alerts to custom handlers:
```bash
PYTHONPATH=src python scripts/hydra_alert_forwarder.py --format json --limit 1 | \
  curl -X POST -H 'Content-Type: application/json' \
  -d @- https://monitoring.example.com/hydra/alerts
```

## Validation Checklist
1. **Success Reset** – Trigger a real Codex resume; ensure failure count resets (`resume_failure_count == 0`).
2. **Failure Alert** – Intentionally resume an invalid session id; confirm `resume_alert` event is created and warning appears in logs.
3. **Telemetry Cross-check** – Compare `hydra_diag metrics` output with `alerts --limit` to verify `active_alert_count` matches persisted alerts.
4. **Forwarder Integration** – Run the forwarder command above and verify the destination receives the alert payload (log file, webhook, etc.).

## Configuration Reference
- `HYDRA_RESUME_ALERT_THRESHOLD`: Minimum consecutive failures before alert is logged/persisted.
- `hydra_alert_forwarder.py`: CLI bridge between persisted alerts and external monitoring systems.
- `scripts/hydra_diag.py alerts`: Diagnostic command for manual inspection or scripting.

Keep this file updated as monitoring integrations evolve.
