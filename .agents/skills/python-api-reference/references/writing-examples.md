# Writing examples

These counterexamples are generalized from rejected SDK edits, not verbatim quotations. `workkit` and `reportkit` are fictional APIs used to illustrate writing choices. Their behavior is stipulated here; real documentation must use verified public APIs. The OpenAI Agents SDK calls in the adapter pair are real.

## Package hierarchy and tone

**DON'T, root:**

> Workkit offers powerful discovery, routing, messaging, work tracking and seamless framework integration. Sessions manage mailboxes, connection leases and delivery queues. The package exports Worker, Workspace, Session, Mailbox, Job and Result.

**DO, root:**

> Let your agents ask other agents for help from Python. A workspace is a shared group of workers; each worker handles requests using your existing harness.

The purpose comes first. Only two local nouns need explaining. Keep feature catalogs, low-level machinery and duplicated generated symbol lists out of the introduction.

**DON'T, subpackage:**

> Use `submit` to create reports, `get` to fetch reports, `wait` to await reports, and `cancel` to cancel them. See the client page for the setup used below.

**DO, subpackage:**

> Run reports against your saved datasets. You need an open `ReportClient` and a dataset ID. Use `client.reports` to request a report and retrieve its result when it finishes.

This gives the area a purpose, names prerequisites locally and explains how to use it without a method inventory. A conceptual or setup-guide link can help, but another page's example must not be a hidden prerequisite.

**DON'T, leaf module:**

> Utilities and classes for the SDK.

**DO, leaf module:**

> Report records returned by the reporting service.

Keep state and field details on the relevant types unless the module needs them to explain its role.

## Class role and ownership

**DON'T:**

> The constructor initializes an internal client, stores the request ID and attaches the transport before setting up callbacks.

**DO:**

> A request your worker is handling. The SDK passes it to your handler; use it to send progress or return a result. It remains valid until the handler returns.

For a class callers instantiate, explain creation and cleanup instead. For a base class, name the method to implement and explain how the SDK uses its return value. Document lifecycle restrictions that affect the caller.

## Show the real framework boundary

**DON'T:** Build a root-page application with a fabricated `Completion` or `ToolCall` schema, a hand-written model loop, provider setup and startup plumbing. An `EchoWorker` that merely returns its input also hides why a harness adapter is useful.

**DO:** For an existing configured OpenAI Agents SDK `existing_agent`, in an async context:

```python
from agents import Runner
from workkit import Worker

class SupportWorker(Worker):
    async def handle(self, request):
        result = await Runner.run(existing_agent, request.text)
        return result.final_output
```

The fictional `Worker` contract accepts the harness output as its handler result. This fragment shows how an existing harness handles SDK requests without teaching how to build that harness. A root page can omit the example entirely when its purpose is already clear.

`Runner.run` and `final_output` were checked in the pinned official [runner source](https://github.com/openai/openai-agents-python/blob/125efa029b4bfd84238bd2c4fd69c3406f802663/src/agents/run.py) and [result source](https://github.com/openai/openai-agents-python/blob/125efa029b4bfd84238bd2c4fd69c3406f802663/src/agents/result.py). This mixed fictional/real illustration was not executed. Verify the relevant version and actual adapter contract before publishing an integration example.

**DON'T, tools:** Show only generated tool schemas, or imply that opening a connection makes those tools available to the harness.

**DO:** For an open fictional `workspace` and configured `existing_agent`, in an async context:

```python
from agents import Runner
from workkit.integrations import workspace_tools

tools = workspace_tools(workspace)
agent = existing_agent.clone(tools=[*existing_agent.tools, *tools])
result = await Runner.run(agent, "Ask a billing worker to review invoice INV-42.")
print(result.final_output)
```

Here the fictional adapter returns tools accepted by the framework. The real `tools` field and `clone` call are documented in the pinned [agent source](https://github.com/openai/openai-agents-python/blob/125efa029b4bfd84238bd2c4fd69c3406f802663/src/agents/agent.py). Explicit installation teaches the integration boundary. Different SDKs install capabilities differently; describe the actual contract. Put credentials, service startup and full lifecycle setup in a guide unless they are the API under discussion.

## Useful inputs and results

**DON'T:**

```python
client.find("anything")  # []
client.tell(worker_id, "hello")
client.get_entry(worker_id)
client.history(request_id)
client.get_result(request_id)
```

These snippets show call syntax without a useful selection, request or result. A canned miss also hides what successful discovery returns.

**DO:** For an open fictional `client` with workers registered for billing:

```python
matches = client.find("review overdue invoices")
if matches:
    request = client.submit_request(matches[0].id, "Review invoice INV-42 for duplicate charges.")
    print(request.id)  # Save this ID to retrieve the review later.
```

The fictional `submit_request` returns a request handle for later result retrieval. For a lookup or history call with no non-obvious choice to teach, keep the contract and omit the example. Each fragment names its own assumptions. Keep branches required for safe result access, even when trimming, as in `Reports.wait` below. Use illustrative output only when its content explains something; never promise an exact model answer.

## Method contract without an application

**DON'T:** Repeat the timeout default in prose, Args and Returns, then embed a full async runner with repeated polling or background relay tasks under `wait`.

**DO, fictional `Reports.wait` docstring:**

````text
"""Wait for a report to finish.

The report keeps running if the wait ends first.

Args:
    report_id: ID of a submitted report.
    timeout: Maximum wait in seconds. Zero checks without waiting.

Returns:
    The latest record, which may still be pending.

Raises:
    ReportNotFoundError: The client cannot access a report with this ID.

Examples:
    For an open `client` and `report_id`, the ID of a submitted sales report:

    ```python
    report = client.reports.wait(report_id, timeout=5.0)
    if report.status == "ready":
        print(report.download_url)
    elif report.status == "failed":
        print(report.error)
    else:
        print("Sales report still pending")
    ```
"""
````

The signature carries the default. The prose and sections explain distinct parts of the contract. Keep argument constraints, errors and result states that change how callers use the method.

## Deferred callbacks

**DON'T:** Teach event-loop scheduling, task cancellation and a complete worker application just to show a deferred callback.

**DO, handler fragment:** For fictional handler `context`, with an existing workflow that saves the returned handle for its completion callback:

```python
pending = context.defer()
```

**DO, callback fragment:** In that workflow's async completion callback, with the saved `pending` handle and completed invoice `review`:

```python
await pending.reply(review)
```

The stipulated contract requires the workflow to finish the deferred request with a reply, failure or rejection; saving the handle alone does not complete it. Describe the actual completion and error operations in real documentation. Keep this semantic requirement in the method contract. Show scheduling or a loop when the API itself requires callers to manage it. Test setup can supply the workflow; reference pages need not recreate it.

## Keep the deployment boundary and verify the claim

These pairs generalize additional reference-review failures.

**DON'T:** “Workers elsewhere connect to the URL from `serve`.”

**DO:** “Workers on the same machine connect to the loopback URL from `serve`. To accept workers on other hosts, run the returned ASGI app on your server.”

Use that wording only for an API with those actual boundaries. Keep the caller's
choice visible; put detailed authentication rules beside the hosting contract,
without repeating the whole explanation on the module and class introductions.

**DON'T:** Present a start/connect/immediate-stop fragment as a useful collaboration example, while its test fixture silently closes the connected client afterward.

**DO:** Show the resource in use between opening and closing it, or label the fragment as acquisition only and state who closes each resource. Existing application objects can supply the work; a full application runner is unnecessary.

**DON'T:** Claim that rejecting a second user proves an invite is single-use when the invite was already restricted to the first user's identity.

**DO:** Test identity binding and first-use consumption separately. Verify any permitted reconnect with the admitted identity. Preserve that distinction in the contract without adding the test procedure to the reference.

**DON'T:** Accept a clean introduction while the rendered page adds empty headings for every constructor assignment and lists internal queue helpers as everyday APIs.

**DO:** Review the page as a reader sees it. Keep useful configuration documented once. Propose audience separation or internal visibility changes with caller evidence; retain supported extension contracts and do not delete implementation merely to shorten navigation.

## Assume the signature has been read

Generalized from redundant constructor and storage docstrings found in review:

| DON'T | DO |
| --- | --- |
| `port: TCP port. 0 when omitted.` | `port: Zero lets the OS choose an available port.` |
| `key: Document key.` under `get(key: str)` | Omit the entry when the key needs no format or scope explanation. |
| `timeout_seconds: Timeout in seconds. Defaults to 25.` | Explain what times out and whether work continues; omit the repeated value and unit. |
| `Returns: An ApplyResult.` | Explain atomic rollback or conflict meaning once, if the summary has not already done so. |
| `model: Model id. Defaults to model-small.` | Omit it unless supported models or a special interpretation need explanation. |

For `get(key: str) -> Any | None`, “Return a copy of the stored value; None means
the key is missing” adds ownership and missing-value semantics. A second Returns
section repeating that sentence does not. For batch reads, order, duplicates and
snapshot guarantees matter; the implementation's loop does not.

Keep meaningful extension contracts even when they are technical. Being an
advanced API is not a reason to narrate its implementation or repeat its signature.


## Do not repair a weak contract with prose

| DON'T | DO |
| --- | --- |
| Annotate `challenge: Mapping[str, Any]`, then describe a known `Challenge` model in Args. | Use `Challenge` inside typed code; parse raw input once at the boundary. If signatures are outside scope, report the mismatch. |
| Declare `get_result() -> dict` when the implementation returns a `JobResult` model. | Make the annotation and delivered reference match the actual supported result. |
| Merge a ranked card, full record and per-item batch error because they share fields. | Retain distinct consumer contracts; remove a projection only after checking producers, callers and compatibility. |
| Treat every model-docstring edit as website-only prose. | Inspect schema descriptions too when tools consume the model schema. |

Raw JSON, arbitrary user content and third-party adapters can legitimately be
open-shaped. Type annotations alone do not validate input or replace authorization,
signature verification, expiry or ownership checks.
