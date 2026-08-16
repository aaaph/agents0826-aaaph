"""Реєстр модулів курсу — до модуля 2 включно."""

from modules import (
    m01_core,
    m02_rag,
)

MODULES = {
    1: m01_core,
    2: m02_rag,
}

__all__ = ["MODULES"]
