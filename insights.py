"""Penjelasan grafik dalam bahasa Indonesia; teks mengikuti angka hasil simulasi."""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

from simulation import (DISTURBANCE_TIME, IMPULSE_WIDTH, RAMP_SLOPE, SINE_PERIOD, STEP_TIME,
                        TEMP_HOT, TEMP_WARM, Params, Scenario, full_load_steady, min_fan_for, status_of)

STATUS_LABEL = {"aman": "Aman", "hangat": "Hangat", "panas": "Panas"}
STATUS_TONE = {"aman": "good", "hangat": "warn", "panas": "hot"}
NBSP = " "  # angka dan satuannya tidak boleh terpisah antar baris


def num(value: float, digits: int = 1) -> str:
    """Format angka berkoma desimal, mis. 74,9."""
    return f"{value:.{digits}f}".replace(".", ",")


def card(tone: str, title: str, text: str) -> dict:
    return {"tone": tone, "title": title, "text": text.replace(" °C", f"{NBSP}°C")}


def _value_at(data: dict, time: float) -> float | None:
    return next((v for t, v in zip(data["t"], data["temperature"]) if t >= time), None)


def _time_to_63(data: dict, start: float, begin: float, steady: float) -> str:
    """Kalimat tentang waktu mencapai 63% perubahan (≈ satu konstanta waktu)."""
    target = begin + 0.632 * (steady - begin)
    rising = steady >= begin
    reached = next((t for t, v in zip(data["t"], data["temperature"])
                    if t >= start and (v >= target if rising else v <= target)), None)
    if reached is None:
        return f"Perubahan 63% ({num(target)} °C) belum tercapai dalam waktu simulasi."
    return (f"Perubahan 63% ({num(target)} °C) tercapai di detik {num(reached, 0)}, "
            f"yaitu {num(reached - start, 0)} detik setelah perubahan (≈ τ).")


@dataclass(frozen=True)
class Cycle:
    """Statistik siklus terakhir pada skenario sinusoida."""
    mean: float
    amplitude: float
    lag: float  # keterlambatan puncak suhu terhadap puncak beban (detik)


def _last_cycle(data: dict) -> Cycle:
    start = data["t"][-1] - SINE_PERIOD
    rows = [(t, v, u) for t, v, u in zip(data["t"], data["temperature"], data["load"]) if t >= start]
    times, temps, loads = zip(*rows)
    peak_temp_time = times[temps.index(max(temps))]
    peak_load_time = times[loads.index(max(loads))]
    return Cycle(sum(temps) / len(temps), (max(temps) - min(temps)) / 2, (peak_temp_time - peak_load_time) % SINE_PERIOD)


def _idle(p, data):
    amb, tau = p.t_amb, data["metrics"]["tau"]
    return ("CPU idle, suhu turun",
            f"CPU mulai di {num(p.t0)} °C dengan beban 0%. Suhu turun cepat dulu (laju awal {num(p.k * (p.t0 - amb), 2)} °C/detik), "
            f"lalu melambat menuju suhu ruangan {num(amb)} °C. Setelah satu konstanta waktu (τ = {num(tau)} detik) "
            f"suhu tinggal {num(amb + (p.t0 - amb) * math.exp(-1))} °C, yaitu sisa 36,8% dari selisih awal.")


def _step(p, data):
    return ("Beban naik mendadak",
            f"Pada detik {STEP_TIME} beban melonjak dari 0% ke 100%. Suhu naik dari {num(data['temperature'][0])} °C menuju steady state "
            f"{num(data['steady'])} °C. {_time_to_63(data, STEP_TIME, p.t_amb, data['steady'])}")


def _impulse(p, data):
    m = data["metrics"]
    return ("Beban hanya sebentar",
            f"Beban 100% hanya menyala {IMPULSE_WIDTH} detik. Suhu sempat naik {num(m['peak'] - p.t_amb)} °C sampai {num(m['peak'])} °C "
            f"di detik {num(m['t_peak'], 0)}, lalu kembali turun menuju {num(p.t_amb)} °C karena energi panasnya kecil.")


def _ramp(p, data):
    full_at = STEP_TIME + 100 / RAMP_SLOPE
    at_full = _value_at(data, full_at)
    tail = (f"Saat beban penuh di detik {num(full_at, 0)}, suhu baru {num(at_full)} °C"
            if at_full is not None else "Beban belum penuh di akhir simulasi")
    return ("Beban naik bertahap",
            f"Beban naik {num(RAMP_SLOPE, 0)}% tiap detik mulai detik {STEP_TIME}. Suhu naik tertinggal dari beban. {tail}, "
            f"lalu menuju steady state {num(data['steady'])} °C.")


def _sine(p, data):
    cycle = _last_cycle(data)
    return ("Beban naik-turun",
            f"Beban berayun 0–100% dengan periode {SINE_PERIOD} detik. Suhu ikut berayun di sekitar {num(cycle.mean)} °C "
            f"(teori {num(data['steady'])} °C) dengan amplitudo ±{num(cycle.amplitude)} °C, jauh lebih kecil dari ayunan beban. "
            f"Puncak suhu tertinggal ±{num(cycle.lag, 0)} detik dari puncak beban.")


def _disturbance(p, data):
    if p.d_amb == 0:
        return ("Tidak ada gangguan", "Kenaikan suhu ruangan diatur 0 °C, sehingga CPU tetap datar di suhu ruangan.")
    return ("Ruangan memanas",
            f"Beban 0%, tetapi pada detik {DISTURBANCE_TIME} suhu ruangan naik {num(p.d_amb, 0)} °C menjadi {num(p.t_amb + p.d_amb)} °C. "
            f"CPU ikut menghangat menuju {num(data['steady'])} °C. {_time_to_63(data, DISTURBANCE_TIME, p.t_amb, data['steady'])}")


WHAT_HAPPENS = {"steady": _idle, "step": _step, "impulse": _impulse, "ramp": _ramp, "sine": _sine, "disturbance": _disturbance}


def _steady_reading(sc: Scenario, data: dict) -> tuple[str, str]:
    m, steady = data["metrics"], data["steady"]
    if sc.key == "sine":
        mean = _last_cycle(data).mean
        return ("Rata-rata vs teori",
                f"Rata-rata suhu pada siklus terakhir {num(mean)} °C, teori {num(steady)} °C (selisih {num(abs(mean - steady), 2)} °C).")
    diff = abs(m["final"] - steady)
    span = max(abs(steady - data["temperature"][0]), 1.0)
    if diff <= 0.02 * span:
        return ("Steady state tercapai",
                f"Suhu akhir {num(m['final'])} °C sudah menempel pada steady state teori {num(steady)} °C (selisih {num(diff, 2)} °C).")
    return ("Belum steady state",
            f"Suhu akhir {num(m['final'])} °C masih {num(diff)} °C dari steady state {num(steady)} °C. Sistem butuh ±3τ = "
            f"{num(3 * m['tau'], 0)} detik setelah perubahan terakhir; perpanjang lama simulasi untuk melihatnya.")


def _fan_advice(p: Params) -> tuple[str, str, str]:
    now = full_load_steady(p)
    best = full_load_steady(replace(p, fan=100))
    tone = STATUS_TONE[status_of(now)]
    if p.fan >= 100:
        return (tone, "Kipas sudah maksimal",
                f"Pada beban penuh, suhu steady state {num(now)} °C dan τ = {num(1 / p.k)} detik. "
                "Menurunkannya lagi hanya bisa lewat beban yang lebih ringan atau ruangan yang lebih sejuk.")
    return (tone, "Efek kipas",
            f"Pada beban penuh suhu steady state {num(now)} °C. Kipas 100% menurunkannya menjadi {num(best)} °C "
            f"(turun {num(now - best)} °C) dan mempercepat respon: τ dari {num(1 / p.k)} menjadi {num(1 / replace(p, fan=100).k)} detik.")


def _euler_note(p: Params, data: dict) -> tuple[str, str]:
    err = data["metrics"]["max_error"]
    quality = "sangat teliti" if err < 0.5 else "cukup teliti" if err < 2 else "kurang teliti"
    hint = "" if err < 0.5 else " Perkecil langkah waktu dt untuk menurunkannya."
    return ("Ketelitian Euler",
            f"Dengan dt = {num(p.dt)} detik, selisih terbesar terhadap solusi langkah halus {num(err, 3)} °C ({quality}).{hint}")


def build_insights(p: Params, sc: Scenario, data: dict) -> list[dict]:
    """Kartu penjelasan simulator: {tone, title, text}."""
    m = data["metrics"]
    status = m["status"]
    fan_tone, *fan_card = _fan_advice(p)
    return [
        card(STATUS_TONE[status], f"Status: {STATUS_LABEL[status]}",
             f"Suhu tertinggi {num(m['peak'])} °C tercapai di detik {num(m['t_peak'], 0)}. "
             f"Batas hangat {num(TEMP_WARM, 0)} °C dan panas {num(TEMP_HOT, 0)} °C (nilai ilustrasi)."),
        card("info", *WHAT_HAPPENS[sc.key](p, data)),
        card("info", *_steady_reading(sc, data)),
        card(fan_tone, *fan_card),
        card("info", *_euler_note(p, data)),
    ]


def fan_summary(p: Params) -> list[dict]:
    """Kartu penjelasan halaman kipas (beban penuh 100%)."""
    at = {fan: full_load_steady(replace(p, fan=fan)) for fan in (20, 60, 100)}
    now = full_load_steady(p)
    safe_fan = min_fan_for(p, TEMP_HOT)
    if safe_fan is None:
        safe = ("hot", "Kipas saja tidak cukup",
                f"Bahkan pada kipas 100% suhu steady state {num(at[100])} °C, masih di atas batas panas {num(TEMP_HOT, 0)} °C. "
                "Kurangi beban CPU atau cari ruangan yang lebih sejuk.")
    elif safe_fan <= 20:
        safe = ("good", "Kipas paling pelan sudah aman",
                f"Dengan kipas 20% suhu steady state beban penuh {num(at[20])} °C, masih di bawah batas panas {num(TEMP_HOT, 0)} °C.")
    else:
        safe = ("info", "Kipas minimum agar tidak panas",
                f"Agar suhu beban penuh tetap di bawah {num(TEMP_HOT, 0)} °C, kipas minimal {safe_fan}% "
                f"(suhu steady state {num(full_load_steady(replace(p, fan=safe_fan)))} °C).")
    return [
        card(STATUS_TONE[status_of(now)], f"Kipas {num(p.fan, 0)}% saat ini",
             f"Pada beban penuh CPU mencapai {num(now)} °C ({STATUS_LABEL[status_of(now)].lower()}) dengan τ = {num(1 / p.k)} detik."),
        card("info", "Selisih terbesar vs terkecil",
             f"Kipas 20% memberi {num(at[20])} °C, kipas 100% memberi {num(at[100])} °C. Selisihnya {num(at[20] - at[100])} °C."),
        card("info", "Hasil yang makin kecil",
             f"Menaikkan kipas dari 20% ke 60% menurunkan suhu {num(at[20] - at[60])} °C, tetapi dari 60% ke 100% hanya "
             f"{num(at[60] - at[100])} °C. Pendinginan memakai rumus k = k_base + k_fan × kipas, sedangkan suhu berbanding terbalik dengan k."),
        card(*safe),
    ]
