"""Telegram adapter for Domus.

This subpackage contains everything specific to running Domus as a Telegram
bot (polling, handlers, job-queue schedulers, lifecycle notifications). The
platform-agnostic assistant "brain" lives in :mod:`domus.core`; any other
frontend (desktop/mobile UI, web app) can reuse that core without importing
anything from here.
"""

from domus.telegram_bot.bot import main

__all__ = ["main"]
