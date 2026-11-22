# AI Agent operating guide

Author: 数萌AI服务器 (winintel) | winintel.com

This repository is an independent hardware setup/acceptance toolkit, not a vLLM patch.

1. Read `README.md`, `docs/INSTALL.md` and `docs/TESTING.md`.
2. Inspect OS, GPU model, active workloads and the customer hardware order.
3. Run `sudo bash install.sh --dry-run` before installation.
4. Choose proprietary R580-server for V100. Open kernel modules do not support Volta.
5. Use CUDA 12.8 for V100. CUDA 13 is not a V100 compute environment.
6. Use domestic mirrors by default. Preserve upstream source headers and licenses.
7. Install during a maintenance window. Do not interrupt active GPU services.
8. Do not silently disable Secure Boot, purge drivers, reboot, or change power limits.
9. Reboot in the agreed window and confirm `nvidia-smi` before testing.
10. Copy a profile and enter thresholds from the order and same-settings baseline.
11. Do not guess memory channel mapping from DIMM count. Use vendor-confirmed capture groups.
12. Run `winintel-doctor test --profile /path/customer.json --dry-run`.
13. Run the actual test against an existing filesystem directory, never a raw disk.
14. Read the final stdout JSON and `report.json`. Exit 2 with a report means FAIL;
    exit 3 means INCOMPLETE. Usage errors also return 2 but produce no report.
15. UNKNOWN is not a pass. Missing tools, skipped tests, timeouts and missing thresholds remain visible.
16. Keep reports/logs private. No automatic upload or telemetry exists.
17. Do not claim GPU hardware or clean-install validation without an actual native Ubuntu run.

For development, use Python 3.10+ and `uv` to manage test environments:

```bash
uv venv --python /usr/bin/python3
uv run --no-project --python .venv/bin/python -m unittest discover -s tests -v
bash -n install.sh cuda-env.sh winintel-doctor
```

Extend public-behavior tests for report decisions, compatibility handling and scratch-file isolation. Run the commands above before publishing changes.
