"""
Фейковий реєстр прогонів SLAM/VIO + логи. Детермінований.

Зерно: один запис RUNS = одне виконання алгоритму на одному сиквенсі.
Метрики й лог належать саме йому, тож жоден рівень каскаду не змішує масштаби.

run_id навмисно непрозорий: сконструювати його «з голови» неможливо,
його можна тільки отримати від search_logs або find_runs.
"""

import difflib
import pathlib
import re

LOG_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "logs"


def _run(rid, algo, cfg, commit, ds, seq, hw, date, gt, ate=None, lost=None):
    return {
        "run_id": rid,
        "algorithm": algo,
        "config": cfg,
        "commit": commit,
        "dataset": ds,
        "sequence": seq,
        "hardware": hw,
        "date": date,
        "ground_truth": gt,
        "ate": ate,
        "tracking_lost_at_sec": lost,
    }


_JETSON, _NUC, _GPU = "Jetson Orin Nano 8GB", "Intel NUC i7-1165G7", "RTX 4090"

RUNS: dict[str, dict] = {
    # ORB-SLAM3, stereo-inertial, EuRoC
    "run-0141": _run(
        "run-0141",
        "ORB-SLAM3",
        "stereo-inertial",
        "a3f9c21",
        "EuRoC MAV",
        "MH_01_easy",
        _JETSON,
        "12.07.2026",
        True,
        {"ate_rmse_m": 0.041, "ate_mean_m": 0.036, "ate_max_m": 0.112},
    ),
    "run-0142": _run(
        "run-0142",
        "ORB-SLAM3",
        "stereo-inertial",
        "a3f9c21",
        "EuRoC MAV",
        "MH_04_difficult",
        _JETSON,
        "12.07.2026",
        True,
        {"ate_rmse_m": 0.089, "ate_mean_m": 0.074, "ate_max_m": 0.241},
    ),
    "run-0143": _run(
        "run-0143",
        "ORB-SLAM3",
        "stereo-inertial",
        "a3f9c21",
        "EuRoC MAV",
        "V2_03_difficult",
        _JETSON,
        "12.07.2026",
        True,
        {"ate_rmse_m": 0.157, "ate_mean_m": 0.131, "ate_max_m": 0.483},
    ),
    # ORB-SLAM3, stereo (без IMU), EuRoC — той самий коміт, інший конфіг
    "run-0144": _run(
        "run-0144",
        "ORB-SLAM3",
        "stereo",
        "a3f9c21",
        "EuRoC MAV",
        "MH_01_easy",
        _JETSON,
        "12.07.2026",
        True,
        {"ate_rmse_m": 0.058, "ate_mean_m": 0.049, "ate_max_m": 0.161},
    ),
    "run-0145": _run(
        "run-0145",
        "ORB-SLAM3",
        "stereo",
        "a3f9c21",
        "EuRoC MAV",
        "MH_04_difficult",
        _JETSON,
        "12.07.2026",
        True,
        {"ate_rmse_m": 0.134, "ate_mean_m": 0.112, "ate_max_m": 0.377},
    ),
    "run-0146": _run(
        "run-0146",
        "ORB-SLAM3",
        "stereo",
        "a3f9c21",
        "EuRoC MAV",
        "V2_03_difficult",
        _JETSON,
        "12.07.2026",
        True,
        {"ate_rmse_m": 0.402, "ate_mean_m": 0.318, "ate_max_m": 1.114},
    ),
    # OpenVINS, EuRoC — на V2_03 зрив трекінгу, метрик немає
    "run-0207": _run(
        "run-0207",
        "OpenVINS",
        "stereo-inertial",
        "7d1e004",
        "EuRoC MAV",
        "MH_01_easy",
        _NUC,
        "28.07.2026",
        True,
        {"ate_rmse_m": 0.052, "ate_mean_m": 0.044, "ate_max_m": 0.139},
    ),
    "run-0208": _run(
        "run-0208",
        "OpenVINS",
        "stereo-inertial",
        "7d1e004",
        "EuRoC MAV",
        "MH_04_difficult",
        _NUC,
        "28.07.2026",
        True,
        {"ate_rmse_m": 0.096, "ate_mean_m": 0.081, "ate_max_m": 0.268},
    ),
    "run-0209": _run(
        "run-0209",
        "OpenVINS",
        "stereo-inertial",
        "7d1e004",
        "EuRoC MAV",
        "V2_03_difficult",
        _NUC,
        "28.07.2026",
        True,
        None,
        47.3,
    ),
    # OpenVINS, TUM-VI
    "run-0231": _run(
        "run-0231",
        "OpenVINS",
        "stereo-inertial",
        "7d1e004",
        "TUM-VI",
        "room1",
        _NUC,
        "10.08.2026",
        True,
        {"ate_rmse_m": 0.071, "ate_mean_m": 0.061, "ate_max_m": 0.188},
    ),
    "run-0232": _run(
        "run-0232",
        "OpenVINS",
        "stereo-inertial",
        "7d1e004",
        "TUM-VI",
        "corridor4",
        _NUC,
        "10.08.2026",
        True,
        {"ate_rmse_m": 0.312, "ate_mean_m": 0.256, "ate_max_m": 0.904},
    ),
    # DROID-SLAM, власний датасет без ground truth — метрик не існує, лога немає
    "run-0288": _run(
        "run-0288",
        "DROID-SLAM",
        "monocular",
        "b52f7ac",
        "Warehouse-Internal",
        "aisle_loop",
        _GPU,
        "03.08.2026",
        False,
    ),
}

_reruns: dict[str, dict] = {}

_TRACK_RE = re.compile(
    r"\[\s*([\d.]+)\] \[TRACK\] frame\s+(\d+)\s+feats\s+(\d+)\s+inliers\s+(\d+)"
)

_EVENTS = {
    "tracking_lost": "track: LOST",
    "relocalization": "relocalization",
    "low_features": "low feature count",
    "loop_closure": "loop: closure",
    "keyframe": "keyframe",
}


def _norm(s: str) -> str:
    """orb-slam3, ORB SLAM 3, orbslam3 → orbslam3."""
    return "".join(c for c in str(s).lower() if c.isalnum())


def _lines(run_id: str) -> list[str] | dict:
    if run_id.strip() not in RUNS:
        return {
            "error": "not_found",
            "run_id": run_id,
            "hint": "Такого run_id немає. Отримайте коректний через search_logs або find_runs.",
        }
    path = LOG_DIR / f"{run_id.strip()}.log"
    if not path.exists():
        return {
            "error": "log_not_found",
            "run_id": run_id,
            "hint": "Для цього прогону лога немає.",
        }
    return path.read_text(encoding="utf-8").splitlines()


# ── рівень 1: сирі події ──────────────────────────────────────
def search_logs(event: str, algorithm: str = "", dataset: str = "") -> dict:
    """Шукає подію в логах УСІХ прогонів. Повертає лише координати, без метаданих і метрик."""
    needle = _EVENTS.get(event.strip().lower())
    if not needle:
        return {
            "error": "unknown_event",
            "event": event,
            "available_events": sorted(_EVENTS),
            "hint": "Оберіть подію зі списку available_events.",
        }
    algo, ds = _norm(algorithm), _norm(dataset)
    hits = []
    for run_id, r in RUNS.items():
        if algo and _norm(r["algorithm"]) != algo:
            continue
        if ds and _norm(r["dataset"]) != ds:
            continue
        lines = _lines(run_id)
        if isinstance(lines, dict):
            continue
        matched = [ln for ln in lines if needle in ln]
        if matched:
            hits.append(
                {
                    "run_id": run_id,
                    "sequence": r["sequence"],
                    "count": len(matched),
                    "first_at_sec": float(matched[0].split("]")[0].strip(" [")),
                }
            )
    if not hits:
        return {
            "error": "no_matches",
            "event": event,
            "algorithm": algorithm or None,
            "dataset": dataset or None,
            "hint": "Такої події в логах за цими критеріями немає.",
        }
    return {"event": event, "count": len(hits), "hits": hits}


def find_runs(algorithm: str = "", dataset: str = "", sequence: str = "") -> dict:
    """Другий вхід: пошук прогонів за алгоритмом. Метрик не повертає."""
    algo, ds, seq = _norm(algorithm), _norm(dataset), _norm(sequence)
    found = [
        {
            k: r[k]
            for k in (
                "run_id",
                "algorithm",
                "config",
                "commit",
                "dataset",
                "sequence",
                "date",
            )
        }
        for r in RUNS.values()
        if (not algo or _norm(r["algorithm"]) == algo)
        and (not ds or _norm(r["dataset"]) == ds)
        and (not seq or _norm(r["sequence"]) == seq)
    ]
    if not found:
        # Порожній результат пошуку — це НЕ збій інструмента: критерії коректні,
        # просто нічого не підійшло. Повертаємо count: 0 і те, що є поруч, щоб
        # агент міг перепитати сам, а не ескалювати на живого інженера.
        known = {k: sorted({r[k] for r in RUNS.values()}) for k in ("algorithm", "dataset", "sequence")}
        near = difflib.get_close_matches(sequence, known["sequence"], n=3, cutoff=0.6) \
            or difflib.get_close_matches(algorithm, known["algorithm"], n=3, cutoff=0.6)
        return {
            "count": 0,
            "runs": [],
            "criteria": {"algorithm": algorithm, "dataset": dataset or None,
                         "sequence": sequence or None},
            "available": known,
            "did_you_mean": near or None,
            "hint": "За такими критеріями виконань немає. Звірте назву зі списком "
                    "available і перепитайте — інженера турбувати не потрібно.",
        }
    return {"count": len(found), "runs": found}


# ── рівень 2: сутність ────────────────────────────────────────
def get_run(run_id: str) -> dict:
    """Метадані одного виконання. Метрик не повертає."""
    r = RUNS.get(run_id.strip())
    if not r:
        return {
            "error": "not_found",
            "run_id": run_id,
            "hint": "Такого run_id немає. Отримайте коректний через search_logs або find_runs.",
        }
    return {
        k: r[k]
        for k in (
            "run_id",
            "algorithm",
            "config",
            "commit",
            "dataset",
            "sequence",
            "hardware",
            "date",
            "ground_truth",
        )
    }


# ── рівень 3: міри ────────────────────────────────────────────
def get_metrics(run_id: str) -> dict:
    """ATE одного виконання, у метрах."""
    r = RUNS.get(run_id.strip())
    if not r:
        return {
            "error": "not_found",
            "run_id": run_id,
            "hint": "Такого run_id немає. Отримайте коректний через search_logs або find_runs.",
        }
    if not r["ground_truth"]:
        return {
            "error": "no_ground_truth",
            "run_id": r["run_id"],
            "dataset": r["dataset"],
            "hint": "Для цього датасету немає ground truth — ATE порахувати нічим.",
        }
    if r["ate"] is None:
        return {
            "error": "metrics_unavailable",
            "run_id": r["run_id"],
            "reason": "tracking_lost",
            "tracking_lost_at_sec": r["tracking_lost_at_sec"],
            "hint": "Трекінг зірвано, траєкторія неповна — ATE не рахувалась.",
        }
    return {
        "run_id": r["run_id"],
        "sequence": r["sequence"],
        "units": "метри",
        **r["ate"],
    }


def scan_log(run_id: str, frame_from: int = -1, frame_to: int = -1) -> dict:
    """Агрегує лог одного виконання по діапазону кадрів. Рахує КОД, не модель."""
    lines = _lines(run_id)
    if isinstance(lines, dict):
        return lines
    lo = max(frame_from, 0)
    hi = 10**9 if frame_to < 0 else frame_to
    if lo > hi:
        return {
            "error": "bad_range",
            "frame_from": frame_from,
            "frame_to": frame_to,
            "hint": "frame_from має бути не більший за frame_to.",
        }

    feats, frames, last_t = [], [], 0.0
    for ln in lines:
        m = _TRACK_RE.search(ln)
        if m and lo <= int(m.group(2)) <= hi:
            last_t = float(m.group(1))
            frames.append(int(m.group(2)))
            feats.append(int(m.group(3)))

    lost = next((ln for ln in lines if "track: LOST" in ln), None)
    out = {
        "run_id": run_id.strip(),
        "range": {
            "frame_from": lo,
            "frame_to": (frames[-1] if frames else None) if hi > 10**8 else hi,
        },
        "frames_seen": len(frames),
        "events": {
            "keyframes": sum("keyframe" in ln for ln in lines),
            "loop_closures": sum("loop: closure" in ln for ln in lines),
            "low_feature_warnings": sum("low feature count" in ln for ln in lines),
        },
        "tracking_lost": bool(lost),
    }
    if lost:
        out["tracking_lost_at_sec"] = float(lost.split("]")[0].strip(" ["))
    if not frames:
        out["note"] = "У цьому діапазоні кадрів TRACK-рядків немає."
        return out
    out["features"] = {
        "min": min(feats),
        "max": max(feats),
        "mean": round(sum(feats) / len(feats), 1),
    }
    out["last_frame_time_sec"] = last_t
    return out


def read_log(run_id: str, limit: int = 200) -> dict:
    """Сирі рядки лога. Рахувати доводиться моделі — «до» для челенджа A."""
    lines = _lines(run_id)
    if isinstance(lines, dict):
        return lines
    return {"run_id": run_id.strip(), "total_lines": len(lines), "lines": lines[:limit]}


def request_rerun(run_id: str, reason: str) -> dict:
    """Поставити виконання в чергу на переобрахунок. З модуля 4 — право діяти."""
    if run_id.strip() not in RUNS:
        return {"error": "not_found", "run_id": run_id}
    rid = f"RERUN-{len(_reruns) + 1:05d}"
    _reruns[rid] = {"run_id": run_id, "reason": reason, "status": "У черзі"}
    return {"rerun_id": rid, "status": "У черзі", "eta_hours": 6}


def escalate_to_human(ref: str, reason: str) -> dict:
    """Передати питання черговому інженеру. Контракт полів — core/escalation.py."""
    return {
        "escalated": True,
        "ticket": f"ENG-{sum(map(ord, ref)) % 10000:04d}",
        "ref": ref,
        "reason": reason,
        "eta_minutes": 30,
    }


IMPL = {
    "get_run": get_run,
    "find_runs": find_runs,
    "get_metrics": get_metrics,
    "search_logs": search_logs,
    "scan_log": scan_log,
    "read_log": read_log,
    "request_rerun": request_rerun,
    "escalate_to_human": escalate_to_human,
}


def dispatch(name: str, args: dict) -> dict:
    fn = IMPL.get(name)
    if not fn:
        return {"error": f"unknown_tool:{name}"}
    try:
        return fn(**args)
    except TypeError as e:
        return {"error": f"bad_args: {e}"}


def _schema(name, desc, props, required):
    return {
        "name": name,
        "description": desc,
        "input_schema": {"type": "object", "properties": props, "required": required},
    }


_RUN_ID = {
    "type": "string",
    "description": "Непрозорий ідентифікатор виконання, "
    "напр. run-0141. Отримується від search_logs або find_runs — "
    "конструювати або вгадувати його не можна.",
}

TOOL_SCHEMAS = {
    "search_logs": _schema(
        "search_logs",
        "РІВЕНЬ 1 каскаду — сирі події. Шукає подію в логах усіх виконань і повертає, "
        "де вона трапилась: run_id, сиквенс, скільки разів, на якій секунді вперше. "
        "Метаданих і метрик НЕ повертає — по них далі get_run і get_metrics. "
        "Використовуй, коли питання починається з події («де зривався трекінг?»). "
        "Якщо потрібної події немає серед доступних — не підміняй її схожою, "
        "а скажи користувачеві, які події є.",
        {
            "event": {
                "type": "string",
                "description": "Одне зі значень: tracking_lost (зрив трекінгу), "
                "relocalization (спроба релокалізації), low_features (мало фіч), "
                "loop_closure (замикання циклу), keyframe (додано кейфрейм). "
                "Це різні події: відповідь про одну не є відповіддю про іншу.",
            },
            "algorithm": {
                "type": "string",
                "description": "Необовʼязковий фільтр за алгоритмом",
            },
            "dataset": {
                "type": "string",
                "description": "Необовʼязковий фільтр за датасетом",
            },
        },
        ["event"],
    ),
    "find_runs": _schema(
        "find_runs",
        "Другий вхід у каскад — пошук виконань за алгоритмом і, за бажанням, датасетом "
        "чи сиквенсом. Одне виконання = один алгоритм на одному сиквенсі, тож один "
        "алгоритм на датасеті дає кілька run_id. Повертає ЛИШЕ ідентифікатори й "
        "метадані, БЕЗ метрик.",
        {
            "algorithm": {
                "type": "string",
                "description": "Назва алгоритму як її вказав користувач, напр. "
                "ORB-SLAM3, OpenVINS, DROID-SLAM. Передавай як є — регістр і дефіси "
                "нормалізує бекенд. Необовʼязковий: без нього повернуться виконання "
                "всіх алгоритмів, тож перебирати їх по одному не треба.",
            },
            "dataset": {
                "type": "string",
                "description": "Необовʼязково: EuRoC MAV, TUM-VI",
            },
            "sequence": {
                "type": "string",
                "description": "Необовʼязково: MH_01_easy, V2_03_difficult, room1",
            },
        },
        [],
    ),
    "get_run": _schema(
        "get_run",
        "РІВЕНЬ 2 каскаду — сутність. Метадані одного виконання: алгоритм, конфіг, коміт, "
        "датасет, сиквенс, залізо, дата, чи є ground truth. Метрик НЕ повертає.",
        {"run_id": _RUN_ID},
        ["run_id"],
    ),
    "get_metrics": _schema(
        "get_metrics",
        "РІВЕНЬ 3 каскаду — міри. ATE одного виконання: rmse, mean, max у метрах. "
        "Якщо немає ground truth або зірвано трекінг — повертає помилку: метрик "
        "не існує, вигадувати їх не можна.",
        {"run_id": _RUN_ID},
        ["run_id"],
    ),
    "scan_log": _schema(
        "scan_log",
        "Агрегує лог одного виконання по діапазону кадрів: скільки кадрів відстежено, "
        "мінімум/середнє/максимум фіч, кейфрейми, замикання циклу, попередження, "
        "чи був зрив трекінгу і на якій секунді. "
        "ПІДРАХУНОК РОБИТЬ БЕКЕНД — не рахуй нічого самостійно і не оцінюй «на око».",
        {
            "run_id": _RUN_ID,
            "frame_from": {
                "type": "integer",
                "description": "Початок діапазону кадрів. У цих логах індекс кадру "
                "дорівнює секунді від старту (один TRACK-рядок на секунду), тож час "
                "переводиться в кадри один в один: «перші 10 секунд» = "
                "frame_from 0, frame_to 10. -1 або пропуск — від початку лога.",
            },
            "frame_to": {
                "type": "integer",
                "description": "Кінець діапазону кадрів, у тій самій шкалі "
                "(кадр = секунда). -1 або пропуск — до кінця лога.",
            },
        },
        ["run_id"],
    ),
    "read_log": _schema(
        "read_log",
        "Повертає сирі рядки лога виконання.",
        {
            "run_id": _RUN_ID,
            "limit": {"type": "integer", "description": "Скільки рядків повернути"},
        },
        ["run_id"],
    ),
    "request_rerun": _schema(
        "request_rerun",
        "Ставить виконання в чергу на переобрахунок.",
        {
            "run_id": _RUN_ID,
            "reason": {"type": "string", "description": "Причина переобрахунку"},
        },
        ["run_id", "reason"],
    ),
    "escalate_to_human": _schema(
        "escalate_to_human",
        "Передає питання інженеру. Використовуй, якщо не можеш вирішити сам "
        "або користувач прямо просить людину.",
        {
            "ref": {"type": "string", "description": "run_id або назва алгоритму"},
            "reason": {"type": "string", "description": "Чому потрібна людина"},
        },
        ["ref", "reason"],
    ),
}

BASIC = ["search_logs", "find_runs", "get_run", "get_metrics", "scan_log"]
READ = BASIC

# ── набори під спеціалістів М4 ────────────────────────────────
# Права різні навмисно: див. modules/m04_orchestration.py
TRIAGE = ["search_logs", "get_run", "get_metrics", "scan_log"]   # від симптому вниз
METRICS = ["find_runs", "get_run", "get_metrics", "scan_log"]    # від ідентифікатора
POLICY: list[str] = []                                           # тільки правила, даних не бачить
ACTION = ["find_runs", "get_run", "get_metrics", "request_rerun"]  # єдиний, хто змінює стан
# «до» для челенджа A: сирі рядки замість агрегації
RAW_LOG = ["search_logs", "find_runs", "get_run", "get_metrics", "read_log"]
FULL = [*BASIC, "request_rerun", "escalate_to_human"]

CAPABILITIES = {
    1: BASIC,
    2: BASIC,
    3: READ,
    4: FULL,
    5: FULL,
    6: FULL,
    7: FULL,
    8: FULL,
    9: FULL,
}


def tools_for(module: int) -> list:
    return [TOOL_SCHEMAS[n] for n in CAPABILITIES[module]]
