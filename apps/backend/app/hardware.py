"""Hardware profiling: CPU, RAM, GPU detection.

Must degrade gracefully — a missing nvidia-smi/rocm-smi, or no GPU at all,
is a normal case (CPU-only), not an error. Full model-recommendation logic
(ARCHITECTURE.md Section 11) lands in Phase 2 once the Model Router exists;
this module only reports what's actually detected.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass, field

import psutil


@dataclass
class GpuInfo:
    vendor: str              # "nvidia" | "amd" | "none"
    name: str | None = None
    vram_total_mb: int | None = None
    backend: str | None = None   # "cuda" | "rocm" | None


@dataclass
class HardwareProfile:
    cpu_model: str
    cpu_cores_physical: int | None
    cpu_cores_logical: int | None
    ram_total_gb: float
    os_name: str
    os_version: str
    gpus: list[GpuInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["gpus"] = [asdict(g) for g in self.gpus]
        return d


def _detect_nvidia() -> list[GpuInfo]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    try:
        out = subprocess.run(
            [exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return []
    gpus = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 2:
            continue
        name, vram = parts
        try:
            vram_mb = int(float(vram))
        except ValueError:
            vram_mb = None
        gpus.append(GpuInfo(vendor="nvidia", name=name, vram_total_mb=vram_mb, backend="cuda"))
    return gpus


def _detect_amd() -> list[GpuInfo]:
    exe = shutil.which("rocm-smi")
    if not exe:
        return []
    try:
        out = subprocess.run(
            [exe, "--showproductname", "--showmeminfo", "vram", "--csv"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return []
    if not out:
        return []
    # rocm-smi output format varies by version; report presence without
    # over-parsing rather than guessing at a fragile format.
    return [GpuInfo(vendor="amd", name="AMD GPU (rocm-smi detected)", backend="rocm")]


def detect_gpus() -> list[GpuInfo]:
    gpus = _detect_nvidia() + _detect_amd()
    return gpus


def get_cpu_model() -> str:
    try:
        return platform.processor() or platform.uname().processor or "unknown"
    except Exception:
        return "unknown"


def profile_hardware() -> HardwareProfile:
    vm = psutil.virtual_memory()
    return HardwareProfile(
        cpu_model=get_cpu_model(),
        cpu_cores_physical=psutil.cpu_count(logical=False),
        cpu_cores_logical=psutil.cpu_count(logical=True),
        ram_total_gb=round(vm.total / (1024 ** 3), 1),
        os_name=platform.system(),
        os_version=platform.version(),
        gpus=detect_gpus(),
    )
