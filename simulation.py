"""Model suhu CPU laptop + kipas (pendinginan Newton + panas dari beban CPU), metode Euler.

    dT/dt = -k (T - T_amb) + g u(t),   k = K_BASE + K_FAN * kipas/100
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, fields, replace

K_BASE = 0.015  # pendinginan alami casing (1/detik)
K_FAN = 0.03    # tambahan pendinginan pada kipas 100% (1/detik)

TEMP_WARM = 60.0  # batas "hangat" (°C), nilai ilustrasi
TEMP_HOT = 80.0   # batas "panas" (°C), nilai ilustrasi

STEP_TIME = 20          # detik
IMPULSE_WIDTH = 5       # detik
RAMP_SLOPE = 2.0        # %/detik
SINE_PERIOD = 100       # detik
DISTURBANCE_TIME = 100  # detik
REFERENCE_STEP = 0.01   # langkah halus untuk solusi pembanding
FAN_LEVELS = (20, 40, 60, 80, 100)


@dataclass(frozen=True)
class Params:
    t0: float = 70.0       # suhu awal CPU (C)
    t_amb: float = 30.0    # suhu ruangan (C)
    fan: float = 50.0      # kecepatan kipas (%)
    g: float = 0.0135      # gain beban (C/detik per % beban)
    dt: float = 1.0        # langkah waktu (detik)
    t_end: float = 300.0   # lama simulasi (detik)
    d_amb: float = 10.0    # kenaikan suhu ruangan pada skenario gangguan (C)

    @property
    def k(self) -> float:
        return K_BASE + K_FAN * self.fan / 100


# (nama, label, min, maks, langkah, satuan, desimal): sumber tunggal untuk validasi dan UI
SLIDERS = (
    ("fan", "Kecepatan kipas", 20, 100, 5, "%", 0),
    ("g", "Gain beban g", 0.005, 0.03, 0.0005, "", 4),
    ("t_amb", "Suhu ruangan", 15, 40, 1, "°C", 0),
    ("t0", "Suhu awal CPU (skenario steady state)", 30, 95, 1, "°C", 0),
    ("d_amb", "Kenaikan suhu ruangan (gangguan)", 0, 15, 1, "°C", 0),
    ("dt", "Langkah waktu (dt)", 0.5, 5, 0.5, "detik", 1),
    ("t_end", "Lama simulasi", 120, 600, 30, "detik", 0),
)
LIMITS = {name: (lo, hi) for name, _, lo, hi, *_ in SLIDERS}
# parameter yang hanya dipakai skenario tertentu (selain itu slider diredupkan di UI)
SLIDER_SCOPE = {"t0": ("steady",), "d_amb": ("disturbance",)}


@dataclass(frozen=True)
class Scenario:
    key: str
    name: str
    color: str
    load: Callable[[float], float]        # sinyal kontrol u(t): beban CPU dalam %
    steady: Callable[[Params], float]     # steady state teori
    start_at_amb: bool = True             # False: CPU mulai dari T0
    disturbed: bool = False               # True: suhu ruangan naik pada DISTURBANCE_TIME
    events: tuple[tuple[float, str], ...] = ()


def _ramp(t: float) -> float:
    return min(max(RAMP_SLOPE * (t - STEP_TIME), 0.0), 100.0)


def _sine(t: float) -> float:
    return 50 + 50 * math.sin(2 * math.pi * t / SINE_PERIOD - math.pi / 2)


def full_load_steady(p: Params) -> float:
    """Steady state bila beban 100% terus-menerus."""
    return p.t_amb + p.g * 100 / p.k


SCENARIOS = {sc.key: sc for sc in (
    Scenario("steady", "Steady state", "#4dabf7", lambda t: 0.0, lambda p: p.t_amb, start_at_amb=False),
    Scenario("step", "Step", "#a78bfa", lambda t: 100.0 if t >= STEP_TIME else 0.0, full_load_steady,
             events=((STEP_TIME, "Beban 100%"),)),
    Scenario("impulse", "Impulse", "#ff6b9d",
             lambda t: 100.0 if STEP_TIME <= t < STEP_TIME + IMPULSE_WIDTH else 0.0, lambda p: p.t_amb,
             events=((STEP_TIME, "Pulsa mulai"), (STEP_TIME + IMPULSE_WIDTH, "Pulsa selesai"))),
    Scenario("ramp", "Ramp", "#ff6b6b", _ramp, full_load_steady,
             events=((STEP_TIME, "Beban mulai naik"), (STEP_TIME + 100 / RAMP_SLOPE, "Beban penuh"))),
    Scenario("sine", "Sinusoida", "#38d9a9", _sine, lambda p: p.t_amb + p.g * 50 / p.k),
    Scenario("disturbance", "Gangguan", "#22b8cf", lambda t: 0.0,
             lambda p: p.t_amb + p.d_amb, disturbed=True, events=((DISTURBANCE_TIME, "Ruangan memanas"),)),
)}

DEFAULT_SCENARIO = "step"

PRESETS = (
    ("Gaming berat", "step", {"fan": 50}, "Beban 100%, kipas 50%"),
    ("Kipas lemah", "step", {"fan": 20}, "Beban 100%, kipas 20%"),
    ("Kipas maksimal", "step", {"fan": 100}, "Beban 100%, kipas 100%"),
    ("Render selesai", "steady", {"t0": 85}, "CPU 85 °C, beban berhenti"),
    ("Ruangan panas", "disturbance", {"t_amb": 30, "d_amb": 15}, "Ruangan naik 15 °C"),
)


def parse_params(raw: dict) -> Params:
    """Bangun Params dari masukan pengguna; nilai di luar rentang ditolak."""
    values = {}
    for field in fields(Params):
        value = float(raw.get(field.name, field.default))
        lo, hi = LIMITS[field.name]
        if not lo <= value <= hi:
            raise ValueError(f"{field.name} harus di antara {lo} dan {hi}")
        values[field.name] = value
    return Params(**values)


def status_of(temp: float) -> str:
    if temp >= TEMP_HOT:
        return "panas"
    return "hangat" if temp >= TEMP_WARM else "aman"


def amb_temp(p: Params, sc: Scenario, t: float) -> float:
    return p.t_amb + (p.d_amb if sc.disturbed and t >= DISTURBANCE_TIME else 0.0)


def integrate(p: Params, sc: Scenario, dt: float, steps: int) -> list[float]:
    temps = [p.t_amb if sc.start_at_amb else p.t0]
    for i in range(steps):
        t = i * dt
        rate = -p.k * (temps[-1] - amb_temp(p, sc, t)) + p.g * sc.load(t)
        temps.append(temps[-1] + rate * dt)  # rumus Euler
    return temps


def fan_curve(p: Params) -> list[dict]:
    """Steady state beban penuh untuk beberapa kecepatan kipas (kipas saat ini ikut ditampilkan)."""
    levels = sorted({*FAN_LEVELS, p.fan})
    rows = []
    for fan in levels:
        q = replace(p, fan=fan)
        steady = full_load_steady(q)
        rows.append({"fan": fan, "steady": steady, "tau": 1 / q.k,
                     "status": status_of(steady), "current": fan == p.fan})
    return rows


def min_fan_for(p: Params, limit: float) -> int | None:
    """Kecepatan kipas terkecil (kelipatan 5%) yang menjaga steady state beban penuh di bawah `limit`."""
    lo, hi = LIMITS["fan"]
    for fan in range(int(lo), int(hi) + 1, 5):
        if full_load_steady(replace(p, fan=fan)) < limit:
            return fan
    return None


def simulate(p: Params, sc: Scenario) -> dict:
    steps = max(1, round(p.t_end / p.dt))
    refine = max(1, round(p.dt / REFERENCE_STEP))
    temps = integrate(p, sc, p.dt, steps)
    reference = integrate(p, sc, p.dt / refine, steps * refine)[::refine]
    times = [i * p.dt for i in range(steps + 1)]
    peak = max(temps)
    steady = sc.steady(p)
    return {
        "t": times,
        "temperature": temps,
        "reference": reference,
        "load": [sc.load(t) for t in times],
        "ambient": [amb_temp(p, sc, t) for t in times],
        "disturbed": sc.disturbed,
        "steady": steady,
        "events": [{"t": t, "label": label} for t, label in sc.events if t <= p.t_end],
        "thresholds": {"warm": TEMP_WARM, "hot": TEMP_HOT},
        "metrics": {
            "peak": peak,
            "t_peak": times[temps.index(peak)],
            "final": temps[-1],
            "steady": steady,
            "tau": 1 / p.k,
            "max_error": max(abs(a - b) for a, b in zip(temps, reference)),
            "status": status_of(peak),
        },
    }
