# Persistent hardware monitoring

Author: 数萌AI服务器 (winintel) | winintel.com

## Install and verify

```bash
sudo bash install-monitor.sh
systemctl is-active winintel-server-monitor.timer
systemctl show winintel-server-monitor.service -p Result -p ExecMainStatus
systemctl list-timers winintel-server-monitor.timer
```

The timer uses `OnCalendar=*:0/30`, `Persistent=true`, no randomized delay, and starts one immediate snapshot at installation. It consumes no GPU compute workload. SMART and kernel reads may take time; a snapshot has a ten-minute service timeout. A snapshot does not change clocks, power limits, drivers, services or disk contents.

The Python runtime is an isolated uv-managed environment. uv is reused if present; otherwise the pinned standalone archive is fetched through the configurable China-accessible mirror. Set `WININTEL_UV_BIN=/path/to/uv` to reuse an existing installation.

## Evidence and alerts

| Evidence | Alert |
|---|---|
| Persistent boot ID | Reboot detected; cause not assumed |
| GPU UUID set | Missing/added/replaced GPUs |
| Supported ECC and retirement counters | Increments, resets and initial uncorrectable/retired pages |
| NVLink CRC/replay/recovery counters | New link errors |
| RAM EDAC counters | Corrected/uncorrected increments |
| Kernel warning/error journal | Includes unrecognized messages for support review |
| SMART health | Disk errors and unavailable health data |
| Failed systemd units | Failed service names |
| Collection result | Missing GPU query or journal access is reported |

State: `/var/lib/winintel-server-doctor/state.json`; append-only local alert log: `alerts.jsonl`; configured delivery queue: `pending.json`. All are private (`0700` directory, `0600` files). The monitor uses a lock and atomic state replacement. The kernel cursor prevents ordinary repeated kernel-message delivery. Persistent bad disk/service conditions are repeated until resolved.

Rotate/archive `alerts.jsonl` according to your support retention policy. State includes private hardware identifiers and raw health evidence. Do not publish it in GitHub.

## Configure your team's receiver

There is no default external destination. Use a **generic HTTPS JSON ingestion endpoint** authorized by the customer. It must accept this schema and return HTTP 2xx after durably receiving the event:

```json
{
  "webhook_url": "https://your-support-domain.example/hardware-alerts",
  "send_heartbeat": true
}
```

Store this in `/etc/winintel-server-doctor/monitor.json`, with mode `0600`. Do not commit production URLs or tokens. The payload contains `brand`, `host`, `time`, `kind` and an `events` array. Hardware/collection anomalies have distinct `kind` values. The receiver can route messages to email, Feishu, Slack or another team channel; those services' native webhook payloads are **not** interchangeable with this generic schema.

```bash
sudo systemctl start winintel-server-monitor.service
sudo journalctl -u winintel-server-monitor.service -n 20 --no-pager
```

Failed HTTP delivery remains queued and retries next check, at most ten queued payloads per run. Endpoints are not printed. Duplicate delivery is possible after a crash; receivers should deduplicate by host/time/event. HTTP 2xx proves receiver acceptance, not human acknowledgement.

## Timing and offline detection

An anomaly is normally reported on the next half-hour check, plus collection/delivery time. This is periodic monitoring, not an instant hardware interrupt or event subscription. After a reboot, the changed boot ID is reported on the first completed snapshot. Failed/unknown collection is never reported as healthy.

Configured heartbeats allow an external receiver to alert if snapshots stop arriving; the receiver must implement that timeout (for example, 45–60 minutes). A local timer cannot report while its server is powered off or disconnected. Persistent kernel journals and BMC logs are needed to investigate a reboot, power failure or hang; some faults leave no surviving software evidence.

To stop monitoring: `sudo systemctl disable --now winintel-server-monitor.timer`. This preserves existing state and reports.
