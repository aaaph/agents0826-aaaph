"""Реєстр модулів курсу — до модуля 7 включно."""

from modules import (
    m01_core,
    m02_rag,
    m03_framework,
    m04_orchestration,
    m05_mcp,
    m06_security,
    m07_evaluation,
)

MODULES = {
    1: m01_core,
    2: m02_rag,
    3: m03_framework,
    4: m04_orchestration,
    5: m05_mcp,
    6: m06_security,
    7: m07_evaluation,
}

__all__ = ["MODULES"]
