# GPU coverage and expansion path

Author: 数萌AI服务器 (winintel) | winintel.com

The current installation/build path targets **V100 SM70**, using proprietary R580-server and CUDA 12.8. Card count is discovered at runtime. Report board identity from the actual SKU, including PCIe/SXM suffixes; do not infer a board generation from slot count or assume all V100s have a 300 W maximum.

## V100 acceptance sequence

1. Record CPU/mainboard/DIMMs/storage/GPU identifiers, firmware, negotiated PCIe links and topology.
2. Confirm no active compute applications, sufficient runtime environment, maximum supported configured GPU power and order-specific targets.
3. Run CUDA deviceQuery and per-GPU pinned H2D/D2H bandwidth.
4. Measure CUDA P2P connectivity, bandwidth and latency; compare both directions on each NVLink-connected pair against a matching topology baseline.
5. Capture supported volatile/aggregate ECC and retirement counters.
6. Run gpu-burn **FP32** then **FP64**, verifying per-GPU OK and completed duration.
7. Run cuda_memtest **tests 0–8 and 10**, reporting allocated MiB and coverage. Enable test 9 explicitly for retention testing.
8. Run NVIDIA matrixMul correctness and double-precision simpleCUBLAS_LU reference/residual validation on every GPU.
9. Compare ECC and link-error counters after all workloads; retain power/utilization/clock telemetry.
10. Install ongoing monitoring and complete a long maintenance-window burn-in before claiming sustained reliability.

The memory suite checks walking bits, own addresses, moving inversions, block moves, random sequences, modulo patterns and stress. The default one pass is a screening run. The upstream documentation recommends 32 passes for complete test6 pattern rotation. Test 9 adds about three hours per pass per GPU. Reserved GPU memory remains inaccessible.

Arithmetic checks exercise the compute path. ECC comes from supported memory/register/cache locations; there is no universal standalone "all CUDA cores ECC" counter. An unsupported location is listed as unavailable, not as zero errors. Tests cannot guarantee detection of every hardware failure.

## NVIDIA family expansion

| Family | Required adaptation / validation | Current status |
|---|---|---|
| Volta V100, PCIe/SXM boards | SM70, CUDA 12.8, proprietary R580; topology-specific floors | Runtime workflow implemented; native 8×SXM2 inventory and tool builds validated; burn-in still requires an idle host |
| Maxwell / Pascal | SM50–SM62, compatible legacy toolkit/driver; optional ECC/NVLink | Future build/profile and hardware validation |
| Turing / Ampere | SM75–SM86, correct driver branch, board-specific ECC/FP64 rate | Future build/profile and hardware validation |
| Ada / Hopper | SM89/SM90, driver/toolkit matching, optional NVSwitch fabric | Future build/profile and hardware validation |
| Blackwell and later | Exact compiler architecture/library support, newer drivers | Future build/profile and hardware validation |
| MIG / vGPU / mixed families | Map CUDA ordinals to physical UUIDs and partitions; isolation-aware testing | Not certified by the current acceptance runner |

Inventory and monitoring collect available NVIDIA fields without hardcoding eight GPUs. This does **not** mean the present SM70 installer has been validated across every NVIDIA product. Family coverage will expand through maintained upstream tools and actual hardware tests, preserving honest UNKNOWN states.
