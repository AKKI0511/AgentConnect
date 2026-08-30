# Hosted Team from a file

``agentconnect.yaml`` names the Team and the Agent classes this process
hosts. ``agentconnect up`` starts the Runtime and joins those Agents.

From this directory::

    poetry run agentconnect up

In another terminal::

    poetry run agentconnect find "someone who can draft a summary"
    poetry run agentconnect ask writer "Draft two paragraphs about the launch."
    poetry run agentconnect trace <trace-id>

``ask`` prints the ``trace_id``. ``trace`` shows accept, lease, and
reply so a failed exchange is visible without reading logs.

Network Agents join this Team with a token::

    poetry run agentconnect token issue --name researcher
