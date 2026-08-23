"""
State management classes for the Telegram agent.

This module contains FSM (Finite State Machine) state classes used for managing
various workflows in the Telegram agent, like announcement creation.
"""

from aiogram.fsm.state import State, StatesGroup


class AnnouncementStates(StatesGroup):
    """States for announcement creation workflow."""

    waiting_for_text = State()
    editing_text = State()
