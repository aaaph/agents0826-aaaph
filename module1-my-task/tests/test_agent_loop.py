"""Логіка agent loop із підміненою моделлю. Мережі немає в жодному тесті."""

import anthropic
import httpx
import pytest
from conftest import response, text_block, tool_block

from core import agent, cost


def test_ok_two_step_chain(fake_model):
    """find_runs → get_metrics → відповідь. Три виклики моделі на два кроки."""
    model = fake_model([
        response([tool_block("find_runs", {"algorithm": "OpenVINS", "dataset": "TUM-VI"})], "tool_use"),
        response([tool_block("get_metrics", {"run_id": "run-0231"}, "toolu_2")], "tool_use"),
        response([text_block("ATE RMSE 0.071 м")], "end_turn"),
    ])
    r = agent.run_agent("system", [{"name": "find_runs"}], "яка ATE?")

    assert r["outcome"] == "ok"
    assert [s["tool"] for s in r["trace"]] == ["find_runs", "get_metrics"]
    assert r["no_tool_used"] is False
    assert len(model.calls) == 3
    # run_id у другому кроці — з результату першого, а не з повітря
    assert r["trace"][1]["input"]["run_id"] in str(r["trace"][0]["output"])


def test_tool_error_is_flagged_and_reaches_the_model(fake_model):
    """Регресія: помилка інструмента має мати is_error=True у tool_result."""
    model = fake_model([
        response([tool_block("get_metrics", {"run_id": "run-0288"})], "tool_use"),
        response([text_block("ground truth немає")], "end_turn"),
    ])
    r = agent.run_agent("system", [{"name": "get_metrics"}], "яка ATE?")

    assert r["outcome"] == "ok"
    assert r["failures"] == [{"tool": "get_metrics", "error": "no_ground_truth"}]
    assert r["trace"][0]["failed"] is True

    tool_result = model.calls[1]["messages"][-1]["content"][0]
    assert tool_result["is_error"] is True, "модель має бачити позначений збій"
    assert "no_ground_truth" in tool_result["content"]


def test_no_tool_used_when_model_answers_from_weights(fake_model):
    fake_model([response([text_block("зазвичай 20–50 фіч")], "end_turn")])
    r = agent.run_agent("system", [{"name": "find_runs"}], "скільки фіч треба?")

    assert r["outcome"] == "ok"
    assert r["no_tool_used"] is True
    assert r["trace"] == []


def test_turns_exhausted_gives_a_defined_answer(fake_model, monkeypatch):
    monkeypatch.setattr(agent, "MAX_TURNS", 2)
    fake_model([
        response([tool_block("find_runs", {"algorithm": "OpenVINS"})], "tool_use"),
        response([tool_block("get_metrics", {"run_id": "run-0231"}, "toolu_2")], "tool_use"),
    ])
    r = agent.run_agent("system", [{"name": "find_runs"}], "яка ATE?")

    assert r["outcome"] == "turns_exhausted"
    assert r["turns"] == 2
    assert r["answer"], "обрив має бути з поясненням, а не порожнім рядком"
    assert len(r["trace"]) == 2, "дані зібрані, забракло кроку на відповідь"


def _api_error(status: int) -> anthropic.APIStatusError:
    """Справжній виняток SDK — щоб перевіряти ту саму гілку, що й у проді."""
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(status, request=request)
    cls = anthropic.NotFoundError if status == 404 else anthropic.APIStatusError
    return cls("boom", response=resp, body=None)


def test_api_error_does_not_crash_the_agent(fake_model):
    fake_model([_api_error(404)] * 3)
    r = agent.run_agent("system", [{"name": "find_runs"}], "яка ATE?")

    assert r["outcome"] == "api_error"
    assert "NotFoundError" in r["error"]
    assert r["answer"]


def test_retries_on_overload_but_not_on_404(fake_model, monkeypatch):
    """529 ретраїться, 404 — ні: повторювати неіснуючу модель немає сенсу."""
    monkeypatch.setattr(agent.time, "sleep", lambda _: None)

    model = fake_model([_api_error(529), response([text_block("ок")], "end_turn")])
    agent._call(model="claude-sonnet-4-6", max_tokens=10, messages=[])
    assert len(model.calls) == 2, "після 529 має бути повторна спроба"

    model = fake_model([_api_error(404), response([text_block("ок")], "end_turn")])
    with pytest.raises(anthropic.NotFoundError):
        agent._call(model="claude-sonnet-4-6", max_tokens=10, messages=[])
    assert len(model.calls) == 1, "404 ретраїти не можна"


def test_parallel_tool_calls_share_one_step(fake_model):
    """Два tool_use в одній відповіді — один крок, обидва результати разом."""
    model = fake_model([
        response([
            tool_block("get_metrics", {"run_id": "run-0141"}, "toolu_1"),
            tool_block("get_metrics", {"run_id": "run-0144"}, "toolu_2"),
        ], "tool_use"),
        response([text_block("порівняння")], "end_turn"),
    ])
    r = agent.run_agent("system", [{"name": "get_metrics"}], "порівняй")

    assert len(r["trace"]) == 2
    assert {s["turn"] for s in r["trace"]} == {0}, "обидва — на нульовому кроці"
    assert len(model.calls) == 2, "паралельні виклики не подовжують маршрут"


# ── вартість і бюджет ─────────────────────────────────────────
def test_token_and_dollar_accounting(fake_model):
    fake_model([
        response([tool_block("find_runs", {"algorithm": "OpenVINS"})], "tool_use", 1000, 100),
        response([text_block("готово")], "end_turn", 2000, 200),
    ])
    agent.run_agent("system", [{"name": "find_runs"}], "яка ATE?")

    assert agent.USAGE["calls"] == 2
    assert agent.USAGE["in"] == 3000
    assert agent.USAGE["out"] == 300
    # 3000/1e6*3.00 + 300/1e6*15.00 = 0.009 + 0.0045
    assert cost.usd(agent.USAGE["by_model"]) == pytest.approx(0.0135)


def test_budget_stops_the_run_and_explains_why(fake_model, monkeypatch):
    monkeypatch.setattr(agent, "MAX_USD", 0.01)
    fake_model([
        # перший виклик коштує 0.0135 — уже понад ліміт
        response([tool_block("find_runs", {"algorithm": "OpenVINS"})], "tool_use", 1000, 100),
        response([tool_block("get_metrics", {"run_id": "run-0231"}, "toolu_2")], "tool_use", 2000, 200),
        response([text_block("не має дійти сюди")], "end_turn"),
    ])
    r = agent.run_agent("system", [{"name": "find_runs"}], "яка ATE?")

    assert r["outcome"] == "budget_exceeded"
    assert r["spent_usd"] >= r["limit_usd"]
    assert "ліміт вартості" in r["answer"] and "$" in r["answer"]
    assert len(r["trace"]) >= 1, "те, що встигли зробити, не викидаємо"


def test_run_completes_when_no_budget_set(fake_model, monkeypatch):
    monkeypatch.setattr(agent, "MAX_USD", 0.0)
    fake_model([
        response([tool_block("find_runs", {"algorithm": "OpenVINS"})], "tool_use", 9_000_000, 0),
        response([text_block("готово")], "end_turn"),
    ])
    r = agent.run_agent("system", [{"name": "find_runs"}], "яка ATE?")
    assert r["outcome"] == "ok"
