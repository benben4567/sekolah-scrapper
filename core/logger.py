"""Emoji-based logging utilities for the DIKMEN scraper."""

from __future__ import annotations

from datetime import datetime
from typing import TextIO
import sys


class EmojiLogger:
    """Simple stdout logger that annotates messages with emoji icons."""

    ICON_MAP = {
        "start": "🚀",
        "province": "🌍",
        "city": "🏙️",
        "district": "📍",
        "school": "🏫",
        "save": "💾",
        "wait": "⏳",
        "warn": "⚠️",
        "error": "❌",
        "info": "ℹ️",
    }

    def __init__(self, stream: TextIO | None = None, time_format: str = "%H:%M:%S") -> None:
        self.stream = stream or sys.stdout
        self.time_format = time_format

    def log(self, level: str, stage: str, message: str) -> None:
        icon = self.ICON_MAP.get(stage, self.ICON_MAP["info"])
        timestamp = datetime.now().strftime(self.time_format)
        line = f"{timestamp} {icon} [{level.upper()}] {message}\n"
        self.stream.write(line)
        self.stream.flush()

    def info(self, stage: str, message: str) -> None:
        self.log("info", stage, message)

    def warn(self, stage: str, message: str) -> None:
        self.log("warn", stage, message)

    def error(self, stage: str, message: str) -> None:
        self.log("error", stage, message)

    def start(self, message: str) -> None:
        self.info("start", message)

    def province(self, message: str) -> None:
        self.info("province", message)

    def city(self, message: str) -> None:
        self.info("city", message)

    def district(self, message: str) -> None:
        self.info("district", message)

    def school(self, message: str) -> None:
        self.info("school", message)

    def save(self, message: str) -> None:
        self.info("save", message)

    def wait(self, message: str) -> None:
        self.info("wait", message)

    def skip(self, message: str) -> None:
        self.warn("warn", message)

    def failure(self, message: str) -> None:
        self.error("error", message)
