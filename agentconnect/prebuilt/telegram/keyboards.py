"""
Keyboard layouts for the Telegram agent.

This module contains the keyboard layouts used in the Telegram agent for
both private and group chats.
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


# Main keyboard for private chats with all options
PRIVATE_CHAT_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="➕ New Announcement"),
            KeyboardButton(text="📜 View Groups"),
        ],
        [KeyboardButton(text="💡 Help"), KeyboardButton(text="🤖 About")],
    ],
    resize_keyboard=True,
)

# Limited keyboard for group chats with only Help and About options
GROUP_CHAT_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="💡 Help"), KeyboardButton(text="🤖 About")]],
    resize_keyboard=True,
)
