"""Бекенд — чисті функції, тестуються без моделі й без мережі взагалі."""

import pytest

from domain import backend as b


def test_chain_cannot_be_bypassed():
    """find_runs не віддає метрик — інакше другий крок був би зайвий."""
    runs = b.find_runs("ORB-SLAM3", "EuRoC MAV")["runs"]
    assert runs
    assert all("ate" not in r and "ate_rmse_m" not in r for r in runs)


def test_algorithm_name_normalisation():
    for name in ("ORB-SLAM3", "orb slam 3", "orbslam3", "  ORB_SLAM3  "):
        assert b.find_runs(name)["count"] == 6, name


def test_empty_search_is_not_a_failure():
    """Регресія челенджа B: одруківка не має ескалювати на інженера."""
    r = b.find_runs("ORB-SLAM3", sequence="MH_02_easy")
    assert "error" not in r, "порожній результат пошуку не є помилкою інструмента"
    assert r["count"] == 0
    assert r["did_you_mean"] == ["MH_01_easy"], "має бути підказка про схожу назву"


def test_invalid_key_is_a_failure():
    """На відміну від порожнього пошуку — тут ключ справді неправильний."""
    assert b.get_metrics("run-9999")["error"] == "not_found"


@pytest.mark.parametrize(
    ("run_id", "expected"),
    [
        ("run-0288", "no_ground_truth"),  # датасет без еталона
        ("run-0209", "metrics_unavailable"),  # трекінг зірвано
    ],
)
def test_missing_metrics_are_stated_explicitly(run_id, expected):
    r = b.get_metrics(run_id)
    assert r["error"] == expected
    assert r["hint"], "помилка без hint не дає моделі що переказати"


def test_metrics_of_a_valid_run():
    r = b.get_metrics("run-0141")
    assert (r["ate_rmse_m"], r["ate_mean_m"], r["ate_max_m"]) == (0.041, 0.036, 0.112)


def test_scan_log_honours_frame_range():
    """Регресія челенджа A: «перші 10 секунд» — це кадри 0–10, не весь лог."""
    part, whole = b.scan_log("run-0209", 0, 10), b.scan_log("run-0209")
    assert part["frames_seen"] == 11
    assert whole["frames_seen"] > part["frames_seen"]
    assert part["features"]["min"] == 131
    assert whole["features"]["min"] == 8, "колапс трекінгу поза діапазоном 0–10"


def test_scan_log_returns_aggregate_not_raw_lines():
    """Агрегат має бути сталого розміру — інакше лог поїде в контекст моделі."""
    assert "lines" not in b.scan_log("run-0141")


def test_events_are_distinct_and_not_substituted():
    """Регресія челенджа B: релокалізація і зрив трекінгу — не одне й те саме."""
    assert "relocalization" in b._EVENTS
    assert b.search_logs("relocalization")["hits"][0]["first_at_sec"] == 47.8
    assert b.search_logs("tracking_lost")["hits"][0]["first_at_sec"] == 47.3


def test_unknown_event_lists_available_ones():
    r = b.search_logs("imu_init")
    assert r["error"] == "unknown_event"
    assert "relocalization" in r["available_events"]


def test_dispatch_rejects_bad_arguments():
    assert b.dispatch("get_metrics", {"нема_такого": 1})["error"].startswith("bad_args")
    assert b.dispatch("немає_інструмента", {})["error"].startswith("unknown_tool")


def test_every_run_has_a_log_or_a_reason_not_to():
    for rid, r in b.RUNS.items():
        lines = b._lines(rid)
        if isinstance(lines, dict):
            assert not r["ground_truth"], f"{rid}: лога немає, хоча прогін валідний"
        else:
            assert any("[TRACK]" in ln for ln in lines), rid
