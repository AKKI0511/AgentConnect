HumanAgent
==========

.. _human_agent:

:class:`~agentconnect.prebuilt.HumanAgent` is a :class:`~agentconnect.agent.base.BaseAgent` that prints incoming work and reads a reply from stdin.

Install the extra first::

    pip install 'agentconnect[cli]'

When to use it
--------------

Use ``HumanAgent`` when a person should sit on a Team in a terminal: reviews, demos, or a typed reply to a teammate.

Subclass ``BaseAgent`` for a non-terminal surface (web UI, Slack, email).

Talk to a teammate
------------------

Join a Team, then ``start_interaction`` until you type ``exit``.

.. code-block:: python

    from agentconnect.prebuilt import AIAgent, HumanAgent
    from agentconnect.team import Team

    async def main():
        team = await Team("content-squad").start()
        human = HumanAgent(name="operator-human")
        assistant = AIAgent(name="assistant", model="gpt-4o-mini")
        await human.join(team)
        await assistant.join(team)
        await human.start_interaction("assistant")

Incoming work
-------------

``process_message`` prints the sender and content, then waits for a line.
Empty input declines a request. ``exit``, ``quit``, or ``bye`` also decline.

Constructor
-----------

- ``name``: Agent name, unique within the Team
- ``prompt``: stdin prompt (default ``You: ``)

See :mod:`agentconnect.prebuilt.human_agent`.
