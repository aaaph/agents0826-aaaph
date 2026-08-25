"""Спільне для тестів: шлях до пакета й фейкова модель.

Жоден тест звідси не ходить у мережу. Модель підмінена, бекенд справжній —
перевіряємо логіку циклу, а не якість відповідей.
"""

import pathlib
import sys
import types

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


def _block(**kw):
    return types.SimpleNamespace(**kw)


def text_block(text):
    return _block(type="text", text=text)


def tool_block(name, tool_input, block_id="toolu_1"):
    return _block(type="tool_use", name=name, input=tool_input, id=block_id)


def response(blocks, stop_reason, in_tokens=100, out_tokens=20):
    """Мінімальна відповідь Anthropic API, якою її бачить core/agent.py."""
    return _block(
        content=blocks,
        stop_reason=stop_reason,
        usage=_block(input_tokens=in_tokens, output_tokens=out_tokens),
    )


class FakeModel:
    """Віддає заздалегідь складений сценарій відповідей, по одній на виклик."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("модель викликали більше разів, ніж є у сценарії")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def fake_model(monkeypatch):
    """Підміняє client.messages.create у core/agent.py."""

    def install(script):
        from core import agent

        model = FakeModel(script)
        monkeypatch.setattr(agent.client, "messages", model)
        agent.reset_usage()
        return model

    return install
