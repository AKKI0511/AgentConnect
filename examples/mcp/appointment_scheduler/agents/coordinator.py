"""Appointment scheduler Team.

One Team with four members. The coordinator is an ``AIAgent``. The other
three are specialists. Start it with ``agentconnect up`` from this directory.

    poetry run agentconnect up

Then::

    poetry run agentconnect ask coordinator "Find a slot next week for a 30 minute call."
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agentconnect.agent import BaseAgent
from agentconnect.prebuilt import AIAgent, Tool

_DATA = Path(__file__).resolve().parent.parent / "data"
_DOWNLOADS = Path(__file__).resolve().parent.parent / "downloads"
_MODEL = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")


class CalendarInspector(BaseAgent):
    """Returns busy slots from a local calendar file."""

    profile = {
        "summary": "Reads the local calendar and lists busy times.",
        "skills": [
            {
                "name": "calendar_inspect",
                "description": "Return busy slots from the local calendar.",
            }
        ],
        "tags": ["calendar", "scheduling"],
    }

    def __init__(self, name: str = "calendar"):
        super().__init__(name=name)
        self.data_path = _DATA / "calendar.json"

    async def process_message(self, msg: dict[str, Any], ctx: Any) -> Any:
        if msg.kind != "request":
            return None
        busy = []
        if self.data_path.exists():
            busy = json.loads(self.data_path.read_text(encoding="utf-8")).get(
                "busy", []
            )
        return {"busy": busy}


class Availability(BaseAgent):
    """Returns open provider slots."""

    profile = {
        "summary": "Reads provider availability and returns two or three open slots.",
        "skills": [
            {
                "name": "availability",
                "description": "Return open appointment slots.",
            }
        ],
        "tags": ["calendar", "scheduling"],
    }

    def __init__(self, name: str = "availability"):
        super().__init__(name=name)
        self.data_path = _DATA / "availability.json"

    async def process_message(self, msg: dict[str, Any], ctx: Any) -> Any:
        if msg.kind != "request":
            return None
        slots = []
        if self.data_path.exists():
            slots = json.loads(self.data_path.read_text(encoding="utf-8")).get(
                "slots", []
            )
        return {"slots": slots[:3]}


def write_ics(summary: str, start: str) -> str:
    """Write a minimal .ics file under downloads/ and return its path."""
    _DOWNLOADS.mkdir(parents=True, exist_ok=True)
    path = _DOWNLOADS / "appointment.ics"
    path.write_text(
        "BEGIN:VCALENDAR\nBEGIN:VEVENT\n"
        f"SUMMARY:{summary}\nDTSTART:{start}\n"
        "END:VEVENT\nEND:VCALENDAR\n",
        encoding="utf-8",
    )
    return str(path)


class Confirmation(AIAgent):
    """Writes a calendar invite for the chosen slot."""

    profile = {
        "summary": "Writes a calendar invite for a confirmed appointment slot.",
        "skills": [
            {
                "name": "confirm_appointment",
                "description": "Write an .ics invite for a chosen slot.",
            }
        ],
        "tags": ["scheduling"],
    }

    def __init__(self, name: str = "confirmation"):
        super().__init__(
            name=name,
            model=_MODEL,
            instructions=(
                "You confirm appointments. Call write_ics with a short summary "
                "and the chosen start time. Return the file path."
            ),
            tools=[
                Tool(
                    name="write_ics",
                    description="Write a calendar invite and return its path.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string"},
                            "start": {
                                "type": "string",
                                "description": "Start time, ISO-8601.",
                            },
                        },
                        "required": ["summary", "start"],
                    },
                    handler=write_ics,
                )
            ],
        )


class Coordinator(AIAgent):
    """Finds teammates and books a slot."""

    profile = {
        "summary": "Schedules appointments by hiring calendar and availability teammates.",
        "skills": [
            {
                "name": "schedule_appointment",
                "description": "Find a free slot and confirm it.",
            }
        ],
        "tags": ["scheduling", "coordinator"],
    }

    def __init__(self, name: str = "coordinator"):
        super().__init__(
            name=name,
            model=_MODEL,
            instructions=(
                "You schedule appointments. Use find to locate calendar, "
                "availability, and confirmation teammates. Ask calendar for busy "
                "times, availability for open slots, pick a slot that is not busy, "
                "then ask confirmation to write the invite. Return the slot and path."
            ),
        )
