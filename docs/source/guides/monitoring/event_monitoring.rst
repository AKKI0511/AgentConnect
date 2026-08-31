Trace timeline
==============

.. _event_monitoring:

The Runtime records a Trace timeline for each exchange: accepted, ticket opened,
leased, completed, replied, ticket closed. ``get_trace`` returns it.
``agentconnect trace`` prints it.

.. code-block:: bash

    poetry run agentconnect trace <trace_id>

A failed ``ask`` is visible from that timeline without reading logs. Canonical
example: ``examples/communication/trace.py``.

Model-provider dashboards (LiteLLM callbacks, vendor consoles) are outside the
Runtime. They can sit next to Team Trace. They do not replace it.
