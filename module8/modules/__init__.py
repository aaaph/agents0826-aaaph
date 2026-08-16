"""Реєстр модулів курсу — до модуля 8 включно."""

from modules import (
    m01_core,
    m02_rag,
    m03_framework,
    m04_orchestration,
    m05_mcp,
    m06_security,
    m07_evaluation,
    m08_cloud,
    m09_client,
)

MODULES = {
    1: m01_core,
    2: m02_rag,
    3: m03_framework,
    4: m04_orchestration,
    5: m05_mcp,
    6: m06_security,
    7: m07_evaluation,
    8: m08_cloud,
    9: m09_client,
}

__all__ = ["MODULES"]
