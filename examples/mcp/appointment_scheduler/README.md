# Appointment scheduler

One Team. A coordinator finds calendar, availability, and confirmation
teammates through Team tools and books a slot.

From this directory::

    poetry install --extras "aiagent cli"
    poetry run agentconnect up

In another terminal::

    poetry run agentconnect find "someone who can book a meeting"
    poetry run agentconnect ask coordinator "Find a 30 minute slot next week."

Set ``AGENTCONNECT_MODEL`` (LiteLLM id) and a provider key. The coordinator
and confirmation members are ``AIAgent`` instances. Calendar and availability
read JSON under ``data/``. Confirmation writes ``downloads/appointment.ics``.

This is a single Team. Cross-team scheduling is later work.
