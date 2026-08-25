"""Реєстр модулів — до модуля 4 включно."""

from modules import (
    m01_core,
    m02_rag,
    m04_orchestration,
)

MODULES = {
    1: m01_core,
    2: m02_rag,
    4: m04_orchestration,
}

__all__ = ["MODULES"]
