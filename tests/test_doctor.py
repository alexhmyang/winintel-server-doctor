# Author: 数萌AI服务器 (winintel) | winintel.com
"""Guard report decisions that could incorrectly accept faulty customer hardware."""

import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("doctor", ROOT / "doctor.py")
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


class AcceptanceTests(unittest.TestCase):
    def report(self, profile=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name)
        (path / "logs").mkdir()
        return doctor.Report(profile or {}, path)

    def test_missing_threshold_cannot_accept_a_speed(self):
        report = self.report()
        report.minimum("Disk", 99999, "disk_read_mib_s_min")
        self.assertEqual(report.save(), 3)
        self.assertEqual(report.data["overall"], "INCOMPLETE")

    def test_failed_check_takes_precedence_over_unknown(self):
        report = self.report()
        report.check("Missing", "UNKNOWN")
        report.minimum("Disk", 500, "disk_read_mib_s_min")
        report.check("ECC", "FAIL")
        self.assertEqual(report.save(), 2)

    def test_html_escapes_customer_profile_content(self):
        report = self.report({"name": "<script>alert(1)</script>"})
        report.check("GPU", "PASS", actual="<img src=x>", detail="<b>raw</b>")
        report.save()
        text = (report.output / "report.html").read_text()
        self.assertNotIn("<script>alert(1)</script>", text)
        self.assertIn("&lt;script&gt;", text)
        self.assertIn("&lt;img src=x&gt;", text)

    def test_unavailable_and_nonfinite_readings_are_not_numeric(self):
        for value in ("[N/A]", "NaN", "inf", None):
            self.assertIsNone(doctor.number(value))

    def test_profile_typo_and_invalid_threshold_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profile.json"
            for profile in (
                {"gpu_counts": 8}, {"gpu_count": -1},
                {"ram_gib_min": True}, {"gpu_name_contains": 123},
            ):
                path.write_text(json.dumps(profile))
                with self.assertRaises(ValueError):
                    doctor.load_profile(path)

    def test_dimm_inventory_omits_serials_and_empty_slots(self):
        text = """Memory Device
    Size: 32 GB
    Locator: CPU1_CH0_DIMM0
    Bank Locator: CPU1
    Serial Number: PRIVATE-ABC
    Configured Memory Speed: 2666 MT/s
Memory Device
    Size: No Module Installed
    Locator: CPU1_CH1_DIMM0
"""
        rows = doctor.dimms(text)
        self.assertEqual(len(rows), 1)
        self.assertNotIn("PRIVATE-ABC", json.dumps(rows))

    def test_bandwidth_parser_keeps_transfer_directions_separate(self):
        text = """Host to Device Bandwidth, 1 Device(s)
PINNED Memory Transfers
Transfer Size (Bytes) Bandwidth(MB/s)
33554432 12345.6
Device to Host Bandwidth, 1 Device(s)
PINNED Memory Transfers
Transfer Size (Bytes) Bandwidth(MB/s)
33554432 11234.5
"""
        self.assertEqual(doctor.bandwidth_value(text, "Host to Device"), 12345.6)
        self.assertEqual(doctor.bandwidth_value(text, "Device to Host"), 11234.5)
        self.assertIsNone(doctor.bandwidth_value("ERROR", "Host to Device"))

    def test_zero_exit_without_sample_pass_is_not_accepted(self):
        report = self.report()
        report.tool_check("bandwidth", {"returncode": 0}, valid=False)
        self.assertEqual(report.save(), 2)

    def test_timeout_is_incomplete_even_with_partial_output(self):
        report = self.report()
        report.tool_check("stress", {"returncode": 124})
        self.assertEqual(report.save(), 3)

    @unittest.skipUnless(sys.platform == "linux", "Linux process groups required")
    def test_command_timeout_terminates_execution(self):
        result = doctor.run_command(
            [sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1,
        )
        self.assertEqual(result["returncode"], 124)
        self.assertLess(result["seconds"], 5)

    def test_disk_targets_only_unique_scratch_file_and_cleans_it(self):
        report = self.report()
        with tempfile.TemporaryDirectory() as folder:
            protected = Path(folder) / "customer-data.txt"
            protected.write_text("keep me")
            seen = []

            def fake_command(name, argv, **kwargs):
                seen.append(argv)
                return {
                    "returncode": 0,
                    "output": json.dumps({"jobs": [{
                        "error": 0,
                        "read": {"bw_bytes": 1024**2, "iops": 100},
                        "write": {"bw_bytes": 1024**2, "iops": 100},
                    }]}),
                }

            args = argparse.Namespace(disk_path=folder, disk_size_gib=1, seconds=10)
            with patch.object(report, "command", side_effect=fake_command), patch.object(
                doctor.shutil, "disk_usage", return_value=argparse.Namespace(free=10 * 1024**3),
            ):
                doctor.disk_tests(report, args)
            fio_commands = [argv for argv in seen if argv[0] == "fio"]
            self.assertEqual(len(fio_commands), 4)
            for argv in fio_commands:
                target = next(x.split("=", 1)[1] for x in argv if x.startswith("--filename="))
                self.assertTrue(Path(target).parent.name.startswith(".winintel-fio-"))
                self.assertFalse(Path(target).exists())
            self.assertEqual(protected.read_text(), "keep me")
            self.assertEqual(list(Path(folder).iterdir()), [protected])

    def test_channel_mapping_counts_cpu_channel_once_for_two_dimms(self):
        report = self.report({
            "ram_channel_locator_regex": r"CPU(\d+)_CH(\d+)_DIMM\d+",
            "ram_channels_min": 2,
        })
        inv = {
            "gpus": [], "cpu_logical": 1, "ram_gib": 64,
            "dimms_available": True,
            "dimms": [
                {"bank": "CPU1", "locator": "CPU1_CH0_DIMM0", "configured_speed": "2666 MT/s"},
                {"bank": "CPU1", "locator": "CPU1_CH0_DIMM1", "configured_speed": "2666 MT/s"},
                {"bank": "CPU1", "locator": "CPU1_CH1_DIMM0", "configured_speed": "2666 MT/s"},
            ],
            "gpu_query": {"returncode": 127},
        }
        doctor.check_inventory(report, inv)
        channel = next(x for x in report.data["checks"] if x["name"] == "Populated memory channels")
        self.assertEqual(channel["actual"], 2)
        self.assertEqual(channel["status"], "PASS")

    def test_faulty_gpu_burn_with_zero_exit_is_rejected(self):
        report = self.report()
        report.data["inventory"] = {"gpus": [{"index": "0", "pci.bus_id": "00000000:01:00.0"}]}
        outputs = {
            "gpu-processes": "",
            "device-query": "Result = PASS",
            "gpu-0-bandwidth": "Result = PASS",
            "gpu-ecc-before": "0, 0",
            "gpu-ecc-after": "0, 0",
            "gpu-burn-fp32": "GPU 0: FAULTY",
            "gpu-burn-fp64": "GPU 0: OK",
            "gpu-0-vram": "main thread: Program exits",
            "gpu-0-matrix-reference": "Result = PASS",
            "gpu-0-fp64-lu-reference": "TEST SUCCESSFUL",
            "nvlink-after-s": "",
            "nvlink-after-e": "",
            "nvlink-errors-before": "",
        }

        def fake_command(name, argv, **kwargs):
            return {"returncode": 0, "output": outputs[name], "seconds": 10}

        monitor = unittest.mock.Mock()
        with patch.object(report, "command", side_effect=fake_command), patch.object(
            doctor, "pcie", return_value={},
        ), patch.object(doctor.subprocess, "Popen", return_value=monitor):
            doctor.gpu_tests(report, argparse.Namespace(seconds=10))
        check = next(x for x in report.data["checks"] if x["name"] == "GPU 0 FP32 stress correctness")
        self.assertEqual(check["status"], "FAIL")

    def test_nvlink_speed_is_measured_only_on_connected_pairs(self):
        from hardware import matrices, nvlink_pairs

        topo = "        GPU0 GPU1 GPU2\nGPU0 X NV2 SYS\nGPU1 NV2 X SYS\nGPU2 SYS SYS X\n"
        text = """P2P Connectivity Matrix
 D\\D 0 1 2
 0 1 1 0
 1 1 1 0
 2 0 0 1
Unidirectional P2P=Enabled Bandwidth (P2P Writes) Matrix (GB/s)
 D\\D 0 1 2
 0 800 43.2 8.1
 1 42.8 800 8.0
 2 8.1 8.0 800
"""
        self.assertEqual(nvlink_pairs(topo), [("0", "1")])
        parsed = matrices(text)
        self.assertEqual(parsed["P2P Connectivity Matrix"]["0"]["2"], 0)
        self.assertEqual(parsed["Unidirectional P2P=Enabled Bandwidth (P2P Writes) Matrix (GB/s)"]["0"]["1"], 43.2)

    def test_ecc_comparison_tracks_uuid_after_gpu_reordering(self):
        from hardware import counter_changes, gpu_details

        def xml(uuid, value):
            return f"""<nvidia_smi_log><gpu><uuid>{uuid}</uuid>
<product_name>Tesla V100-SXM2-32GB</product_name>
<ecc_errors><volatile><single_bit><device_memory>{value}</device_memory>
</single_bit></volatile></ecc_errors></gpu></nvidia_smi_log>"""

        before = gpu_details(xml("GPU-a", 2))
        after = {"1": gpu_details(xml("GPU-a", 3))["0"]}
        change = counter_changes(before, after)[0]
        self.assertEqual(change["delta"], 1)
        self.assertEqual(change["gpu"], "1")
        self.assertEqual(after["1"]["form_factor"], "SXM2")

    @unittest.skipUnless(sys.platform == "linux", "Monitor requires Linux")
    def test_monitor_detects_reboot_ecc_and_unknown_kernel_errors(self):
        import monitor

        base = {
            "boot_id": "a", "gpu_query_code": 0, "journal_code": 0,
            "gpus": {"0": {"uuid": "GPU-a", "error_counters": {
                "ecc_errors/volatile/single_bit/device_memory": "0",
            }}},
            "kernel_records": [], "edac": {}, "storage": {},
            "nvlink": {"output": ""}, "failed_services": {"returncode": 0, "output": ""},
        }
        current = json.loads(json.dumps(base))
        current["boot_id"] = "b"
        current["gpus"]["0"]["error_counters"]["ecc_errors/volatile/single_bit/device_memory"] = "1"
        current["kernel_records"] = [{"MESSAGE": "unknown platform error", "PRIORITY": "3"}]
        kinds = {event["kind"] for event in monitor.anomalies(base, current)}
        self.assertEqual(kinds, {"REBOOT_DETECTED", "GPU_COUNTER_CHANGED", "KERNEL_WARNING_OR_ERROR"})

    @unittest.skipUnless(sys.platform == "linux", "Monitor requires Linux")
    def test_delivery_failure_keeps_pending_alert_for_retry(self):
        import monitor

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            config = path / "config.json"
            config.write_text('{"webhook_url":"https://example.invalid/receiver"}')
            current = {
                "host": "test", "time": "2026-11-22T00:00:00+00:00",
                "boot_id": "a", "gpu_query_code": 1, "journal_code": 0,
                "gpus": {}, "kernel_records": [], "edac": {}, "storage": {},
                "nvlink": {"output": ""}, "failed_services": {"returncode": 0, "output": ""},
            }
            argv = ["monitor", "--state-dir", folder, "--config", str(config)]
            with patch.object(sys, "argv", argv), patch.object(monitor, "snapshot", return_value=current), patch.object(
                monitor, "deliver", side_effect=OSError("offline"),
            ):
                monitor.main()
            pending = json.loads((path / "pending.json").read_text())
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["events"][0]["kind"], "COLLECTION_FAILED")


if __name__ == "__main__":
    unittest.main()
