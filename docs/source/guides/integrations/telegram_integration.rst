Telegram Integration
====================

.. _telegram_integration:

:class:`~agentconnect.prebuilt.telegram.TelegramAIAgent` is an ``AIAgent`` with a Telegram bot. Join a Team, then ``run()`` to poll Telegram.

Install the extra first::

    pip install 'agentconnect[telegram]'

Create a bot with Telegram ``@BotFather`` and put the token in ``TELEGRAM_BOT_TOKEN`` or pass ``telegram_token``.

Usage
-----

.. code-block:: python

    import os
    from agentconnect.prebuilt import TelegramAIAgent
    from agentconnect.team import Team

    async def main():
        agent = TelegramAIAgent(
            name="telegram-bot",
            model=os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini"),
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        )
        team = await Team("content-squad").start()
        await agent.join(team)
        await agent.run()

``run()`` polls Telegram. The Session already pulls Team work after ``join``.
Incoming Telegram text uses the same LiteLLM loop as Team deliveries.
Telegram send and announcement operations are extra tools.

``groups_file`` (default ``groups.txt``) stores registered group chat ids.

See :mod:`agentconnect.prebuilt.telegram` and ``agentconnect/prebuilt/telegram/README.md``.
