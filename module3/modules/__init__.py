"""Реєстр модулів курсу — до модуля 3 включно."""

from modules import (
    m01_core,
    m02_rag,
    m03_framework,
)

MODULES = {
    1: m01_core,
    2: m02_rag,
    3: m03_framework,
}

__all__ = ["MODULES"]
