"""Deterministic ship-desk specialists.

Replies use Thread history for facts and constraints. They do not echo
the whole transcript. Each Profile names supported work; unsupported
requests decline instead of returning a default document.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from agentconnect import AgentProfile, BaseAgent, Context, MailboxMessage, Skill
from agentconnect.agent.errors import SessionError

FORENSIC_DELAY_SECONDS = 6.0
HEAP_DUMP_DELAY_SECONDS = 8.0
NESTED_METRICS_DELAY_SECONDS = 6.0
PRESS_NOTICE_DELAY_SECONDS = 0.8
LAB_NOTE_SLOW_SECONDS = 0.8
LAB_NOTE_FAST_SECONDS = 0.05

INCIDENT = {
    "incident_id": "INC-4821",
    "service": "payments-api",
    "release": "2.4.1",
    "canary_percent": 10,
    "region": "us-east-1",
    "timeline": [
        {"at": "14:02", "event": "Canary 2.4.1 started at 10% in us-east-1."},
        {"at": "14:11", "event": "p99 checkout latency rose from 180ms to 940ms."},
        {"at": "14:18", "event": "5xx rate on /checkout hit 4.1% (SLO 0.5%)."},
        {"at": "14:22", "event": "Error budget for the remaining 6 hours: 18% left."},
        {
            "at": "14:25",
            "event": "The remaining 90% of traffic stayed on 2.4.0 and was healthy.",
        },
    ],
    "open_sev0_by_region": {
        "us-east-1": ["INC-4821"],
        "eu-west-3": [],
    },
}

CHANGELOG = [
    {
        "id": "PAY-881",
        "risk": "high",
        "summary": "New idempotency key path on /checkout.",
    },
    {
        "id": "PAY-902",
        "risk": "medium",
        "summary": "Retry budget for card processor timeouts.",
    },
    {
        "id": "PAY-910",
        "risk": "low",
        "summary": "Metrics label rename for processor_id.",
    },
    {"id": "PAY-914", "risk": "low", "summary": "Docs fix for refund webhooks."},
    {
        "id": "PAY-918",
        "risk": "medium",
        "summary": "Timeout alignment with the ledger writer.",
    },
    {
        "id": "PAY-921",
        "risk": "low",
        "summary": "Internal admin filter for dispute states.",
    },
    {
        "id": "PAY-924",
        "risk": "high",
        "summary": "Checkout session cache keyed only on account id.",
    },
    {"id": "PAY-927", "risk": "low", "summary": "Log sampling for processor_id."},
    {
        "id": "PAY-931",
        "risk": "medium",
        "summary": "Fallback acquirer order when the primary 5xxs.",
    },
    {"id": "PAY-934", "risk": "low", "summary": "OpenAPI example for refund webhooks."},
    {"id": "PAY-938", "risk": "low", "summary": "CI job rename for payments-api."},
    {
        "id": "PAY-941",
        "risk": "low",
        "summary": "Chart dashboard filter for canary percent.",
    },
    {
        "id": "PAY-944",
        "risk": "low",
        "summary": "Health-check path for the ledger writer sidecar.",
    },
    {
        "id": "PAY-947",
        "risk": "medium",
        "summary": "Card BIN range table refresh during processor failover.",
    },
    {
        "id": "PAY-951",
        "risk": "low",
        "summary": "Dispute evidence upload timeout copy in admin.",
    },
    {
        "id": "PAY-954",
        "risk": "low",
        "summary": "Remove unused feature flag for checkout dark launch.",
    },
    {
        "id": "PAY-958",
        "risk": "medium",
        "summary": "Webhook retry jitter for refund.completed events.",
    },
    {
        "id": "PAY-961",
        "risk": "low",
        "summary": "Internal runbook link on the canary splitter page.",
    },
    {
        "id": "PAY-965",
        "risk": "low",
        "summary": "Processor_id enum alignment in the refunds worker.",
    },
    {
        "id": "PAY-968",
        "risk": "medium",
        "summary": "Checkout span attributes for idempotency store hits.",
    },
    {
        "id": "PAY-972",
        "risk": "low",
        "summary": "Grafana folder move for payments-api SLO boards.",
    },
    {
        "id": "PAY-975",
        "risk": "low",
        "summary": "Pager routing update for us-east-1 checkout pages.",
    },
    {
        "id": "PAY-979",
        "risk": "low",
        "summary": "Terraform comment cleanup on the canary traffic module.",
    },
    {
        "id": "PAY-982",
        "risk": "medium",
        "summary": "Acquirer timeout budget shared with the ledger writer.",
    },
    {
        "id": "PAY-986",
        "risk": "low",
        "summary": "OpenAPI example for dispute webhook signatures.",
    },
    {
        "id": "PAY-989",
        "risk": "low",
        "summary": "Admin CSV export column order for checkout attempts.",
    },
]

METRICS = {
    "service": "payments-api",
    "release": "2.4.1",
    "p99_ms": 940,
    "baseline_p99_ms": 180,
    "error_rate": 0.041,
    "slo_error_rate": 0.005,
    "error_budget_remaining": 0.18,
    "canary_percent": 10,
    "additional_canary_percent": 0,
}

CHANGELOG_PAGE_SIZE = 4
POSTMORTEM_MIN_CHARS = 12000

POSTMORTEM_NOTES = """INC-4821 postmortem — payments-api 2.4.1 canary (us-east-1)

Document class: retained incident notes. This is the desk copy used after the
first hour, not a live ticker. Identifiers, timestamps, and counts below are
the fixture facts for this Team. Do not infer other regions, other releases,
or an executed rollback from this document alone.

1. Executive summary
The 10% canary of payments-api 2.4.1 in us-east-1 breached checkout SLO.
p99 latency moved from 180ms to 940ms, and the /checkout 5xx rate reached
4.1% against a 0.5% SLO. Error budget for the remaining six hours fell to
18%. The other 90% of traffic stayed on 2.4.0 and remained healthy. The
desk recommendation is to hold the canary and not expand it. Preparation of
rollback wording, a request to roll back, or legal hold language is not
proof that 2.4.0 is serving the canary slice again.

Service: payments-api
Release under test: 2.4.1
Baseline release on the remainder: 2.4.0
Canary percent: 10
Additional canary percent after 10%: 0
Region: us-east-1
Incident id: INC-4821
Open SEV0 in eu-west-3: none
Traffic splitter: canary.payments-api.us-east-1
Error budget window remaining at 14:22: six hours, 18% left

2. Detection
Synthetic checkout probes first crossed the latency page at 14:11. The
error-rate page followed at 14:18. On-call confirmed the canary slice in
the traffic splitter before opening INC-4821. Customer-visible retries
increased on card-processor timeouts in the same window. The first human
ack on the checkout pager was 14:12. The traffic-splitter screenshot in
the incident channel showed weight 10 on 2.4.1 and weight 90 on 2.4.0.
No second region appeared in that screenshot.

Probe names that fired:
- synth.checkout.card_ok.us-east-1 (latency page, 14:11)
- synth.checkout.card_ok.us-east-1 (5xx page, 14:18)
- synth.checkout.wallet_ok.us-east-1 (latency warn only, not paged)
- synth.refund.create.us-east-1 (did not page)

3. Timeline
14:02 Canary 2.4.1 started at 10% in us-east-1. Splitter change ticket
      CFG-3318. No overlap with a config freeze.
14:04 First canary pods reported Ready. Replica count 12 in us-east-1a/1b.
14:07 Checkout span rate on the canary deployment rose in line with the
      10% weight. No error-rate move yet.
14:11 p99 checkout latency rose from 180ms to 940ms on the canary
      deployment. Baseline 2.4.0 p99 stayed near 180ms.
14:13 On-call joined. Confirmed the page was canary-scoped, not a total
      site outage.
14:15 Idempotency-store hit rate on canary hosts moved in a way the desk
      cannot prove from metrics alone. Heap-dump symbols exist on a
      delayed path and are not a substitute for traces.
14:18 5xx rate on /checkout hit 4.1% (SLO 0.5%). Processor timeout
      labels dominated the 5xx mix.
14:20 Customer-success queue began receiving “pay now retries twice”
      tickets from us-east-1 card checkout.
14:22 Error budget for the remaining 6 hours: 18% left.
14:25 Remaining 90% of traffic on 2.4.0 stayed healthy. eu-west-3 had no
      open SEV0. us-east-1 listed INC-4821 only.
14:28 Changelog high-risk items identified: PAY-881 and PAY-924.
14:31 Incident desk reconstructed the timeline and asked metrics and
      changelog peers for a hold recommendation.
14:36 Hold recommendation recorded: keep the canary at 10% or below;
      do not expand; do not claim a rollback unless a later confirmed
      status update says the canary has been rolled back to 2.4.0.

4. Impact
Checkout for canary customers was slow or failed. Refunds and non-checkout
admin paths were not implicated in the first hour. eu-west-3 had no open
SEV0. us-east-1 listed INC-4821 only. No evidence in this desk that other
regions received the 2.4.1 canary.

Customer-visible effect, first hour, us-east-1 canary slice only:
- Slow checkout (p99 940ms vs 180ms baseline)
- Elevated 5xx on POST /checkout
- Retry prompts in the web and iOS clients after processor timeouts
- No confirmed duplicate captures in the first hour
- No confirmed lost refunds in the first hour

Approximate volume in the first hour (desk reconstruction, not billing):
- Checkout attempts on canary 2.4.1: about 18,400
- Checkout 5xx on that slice: about 750
- Timeout-classified 5xx: about 610
- Application 4xx (expected declines): unchanged vs baseline
- Refund create on canary: no SLO breach

5. Customer ticket excerpts (redacted)
These are sample notes copied from the support queue. They are not a
complete export.

TCK-10421 14:20 us-east-1 web
“Pay now spun, then said try again. Card was not charged the first time.
Second submit took almost a second and still failed.”

TCK-10428 14:23 us-east-1 iOS
“Wallet pay hung on the confirmation screen. I backed out. Order stayed
unpaid.”

TCK-10433 14:26 us-east-1 web
“Got an error after the 3DS step. Support asked me to wait; I did not
retry a third time.”

TCK-10441 14:29 us-east-1 web
“Checkout felt fine yesterday. Today the spinner sits there. I am on the
same card.”

TCK-10452 14:34 us-east-1 Android
“Two timeouts, then a decline that looks like a processor timeout rather
than insufficient funds.”

Do not treat these tickets as proof that 2.4.0 is unhealthy. They arrived
while the 10% canary was live.

6. SLO snapshot used by the hold call
service: payments-api
release: 2.4.1
p99_ms: 940
baseline_p99_ms: 180
error_rate: 0.041
slo_error_rate: 0.005
error_budget_remaining: 0.18
canary_percent: 10
additional_canary_percent: 0

Read that last field as a valid zero: nothing above 10% rolled. A later
metrics-analyst snapshot should be allowed to repeat 0 without that being
an empty failure.

7. Trace excerpts
Forensic reconstruction repeats the same timeline from traces after a
short delay and includes span-8f21. The notes below are the retained
shape, not a live trace store.

span-8f21  checkout_handler  14:11:03  938ms  status=error
  http.route=/checkout
  http.method=POST
  release=2.4.1
  canary=true
  region=us-east-1
  error=processor_timeout
  child: idempotency_store.lookup  14:11:03  410ms
  child: card_processor.authorize    14:11:03  480ms  timeout

span-8f44  checkout_handler  14:18:11  910ms  status=error
  same route, release 2.4.1, canary=true
  error=processor_timeout
  child: idempotency_store.lookup  390ms
  child: card_processor.authorize    470ms  timeout

span-9021  checkout_handler  14:25:40  176ms  status=ok
  release=2.4.0
  canary=false
  region=us-east-1
  This span is the remainder, not the canary. Do not average it into the
  canary p99.

Heap-dump symbol notes, when collected on the delayed path, list
checkout_handler and idempotency_store. They do not prove cache collisions.
Ask incident-triage for that delayed path; metrics-analyst cannot decode
a heap dump.

8. Contributing changes in 2.4.1
PAY-881 (high): new idempotency key path on /checkout.
PAY-924 (high): checkout session cache keyed only on account id.

Medium items that touch retry, timeouts, or acquirer order, but are
secondary relative to the two high-risk checkout changes:
PAY-902 Retry budget for card processor timeouts.
PAY-918 Timeout alignment with the ledger writer.
PAY-931 Fallback acquirer order when the primary 5xxs.
PAY-947 Card BIN range table refresh during processor failover.
PAY-958 Webhook retry jitter for refund.completed events.
PAY-968 Checkout span attributes for idempotency store hits.
PAY-982 Acquirer timeout budget shared with the ledger writer.

Low-risk items in 2.4.1 include docs, metrics labels, admin filters, CI
renames, OpenAPI examples, dashboard filters, health-check paths, and
pager routing. They are in the changelog. They are not the hold reason.

The changelog is paged. High-risk filter returns PAY-881 and PAY-924.
An explicit reset is required before listing the rest on the same
conversation. After that reset, “next page” should continue the
unfiltered list on that same conversation.

9. Meeting notes (14:31 desk)
Attendees: incident-triage, metrics-analyst (async), changelog-scribe
(async), risk-reviewer (optional overlap), press-liaison (comms only).

Decision recorded: hold_canary. Reason recorded: p99 and 5xx exceeded
SLO while the remaining 90% on 2.4.0 stayed healthy.

Not decided in this meeting: executing a rollback. Legal may send hold
language. Someone may ask press-liaison to prepare rollback wording.
Neither of those is a confirmed status that the canary has been rolled
back to 2.4.0.

Press constraint: drafts should say checkout is slower than usual for
some payments-api customers on canary 2.4.1 and that the rollout is
held. If legal sends hold language, the draft must say the canary will
not expand. If a confirmed rollback notice arrives, the draft may say
the canary has been rolled back to 2.4.0. A request to roll back is
not that confirmation.

10. Runbook excerpt (payments-api canary, us-east-1)
1. Confirm the page is scoped to the canary deployment, not 2.4.0.
2. Read p99, 5xx, error budget remaining, and additional canary percent.
3. List high-risk 2.4.1 changes. Reset the changelog filter if you need
   the full list on the same Thread.
4. Recommend hold if SLO is breached and the remainder is healthy.
5. Do not expand the canary.
6. Do not tell customers that other regions are unaffected unless a
   specialist result says so.
7. Do not publish “we are rolling the canary back” from a preparation
   note or from “do not rollback”.
8. Collect delayed forensics by ticket id if wait returns open.

Commands operators actually ran in the first hour (copied from the
shell history paste in the incident channel):

kubectl -n payments get deploy payments-api-canary -o wide
kubectl -n payments get deploy payments-api-stable -o wide
# canary: 12 ready, image payments-api:2.4.1
# stable: remainder, image payments-api:2.4.0

curl -sS "$SPLITTER/v1/weights" | jq '.us_east_1'
# {"canary": 10, "stable": 90, "release_canary": "2.4.1"}

11. Open questions
Whether PAY-924 cache collisions explain the 5xx spike is not proven from
this desk. Heap-dump symbol notes exist on a delayed path and are not a
substitute for traces. Forensic reconstruction repeats the same timeline
from traces after a short delay. Processor-side incident tickets were not
attached in the first hour. Duplicate-capture risk after client retry is
unproven; the idempotency path is the suspect, not a closed finding.

12. Follow-up
Keep the canary at 10% or below until p99 and 5xx return to SLO. Re-read
metrics before any expansion. Reset changelog filters explicitly when a
later reader needs the full 2.4.1 list rather than high-risk items only.
Retain this document for later history paging; it is long on purpose so a
targeted hold recommendation can be compared with a full-notes read.

What this desk can still produce
A delayed forensic reconstruction repeats the same timeline from traces
and includes span-8f21. Heap-dump symbol notes list checkout_handler and
idempotency_store after a longer delay. Metrics can return a valid zero
for additional canary percent. Changelog paging is compact; an explicit
reset is required after a high-risk filter, and the next unfiltered page
belongs on that same Thread. Press drafts change when a supported notice
arrives. Legal hold language means the canary will not expand. A
confirmed rollback notice means the canary has been rolled back to
2.4.0. Preparation or negated rollback wording must not claim that
execution.

13. Support-queue counts (first 40 minutes)
These counts are the desk reconstruction used when comparing a targeted
hold recommendation with this full-notes read. They are not a billing
extract.

- TCK opened with checkout timeout wording: 41
- TCK opened with spinner / “try again”: 27
- TCK opened with 3DS / processor decline wording: 9
- TCK opened for refunds in the same window: 0
- TCK opened from eu-west-3 for this canary: 0
- Duplicate-charge claims in the first hour: 0 confirmed

On-call paste for the error-budget remaining chart at 14:22 showed 18%
left in a six-hour window. The 2.4.0 remainder chart did not move. If a
later reader only needs p99, 5xx, and additional canary percent, use
metrics-analyst instead of this document.
"""


def _as_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        parts = [
            str(content[key])
            for key in ("task", "question", "need", "notice", "text", "message")
            if isinstance(content.get(key), str) and str(content[key]).strip()
        ]
        if parts:
            return " ".join(parts)
        return " ".join(str(value) for value in content.values() if value is not None)
    return str(content)


def _kind(item: Any) -> str:
    return str(getattr(item, "kind", "") or "")


def _item_text(item: Any) -> str:
    return _as_text(getattr(item, "content", None))


def _request_blob(msg: MailboxMessage, ctx: Context) -> str:
    parts = [_as_text(msg.content)]
    for item in ctx.history:
        if _kind(item) == "request":
            parts.append(_item_text(item))
    return " ".join(parts).lower()


def _event_notices(ctx: Context) -> list[str]:
    notices: list[str] = []
    for item in ctx.history:
        if _kind(item) == "event":
            text = _item_text(item).strip()
            if text:
                notices.append(text)
    return notices


def _contains(text: str, *needles: str) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _wants_remaining_health(text: str) -> bool:
    lowered = text.lower()
    mentions_slice = "90" in lowered or "remaining" in lowered
    mentions_health = "healthy" in lowered or "health" in lowered
    return mentions_slice and mentions_health


def _ticket_content(ticket: Any) -> Any:
    response = getattr(ticket, "response", None)
    if response is None:
        return None
    return getattr(response, "content", None)


def _prior_incident_id(ctx: Context) -> str | None:
    for item in ctx.history:
        content = getattr(item, "content", None)
        if isinstance(content, dict):
            value = content.get("incident_id")
            if isinstance(value, str) and value.strip():
                return value
    return None


def _asks_prior_identifier(text: str) -> bool:
    return _contains(
        text,
        "incident identifier",
        "what identifier",
        "already report",
        "identifier did you",
    )


def _is_hold_request(text: str) -> bool:
    return _contains(
        text,
        "should we hold",
        "recommend hold",
        "hold the",
        "hold or ship",
        "hold/ship",
        "go/no-go",
        "go or no-go",
    )


def _is_forensic_request(text: str) -> bool:
    return _contains(text, "forensic", "from traces", "trace reconstruct")


def _is_heap_request(text: str) -> bool:
    return _contains(text, "heap dump", "heap-dump")


def _is_lab_note_request(text: str) -> bool:
    return _contains(text, "lab note", "record this lab observation")


def _is_sev0_request(text: str) -> bool:
    return _contains(text, "sev0", "sev 0")


def _is_timeline_request(text: str) -> bool:
    return _contains(text, "timeline", "reconstruct", "what happened")


_AFTER_TIME = re.compile(
    r"(?:after|from|since|at\s*/\s*after|at\s+or\s+after)\s+(\d{1,2}:\d{2})",
    re.IGNORECASE,
)
_BEFORE_TIME = re.compile(r"\bbefore\s+(\d{1,2}:\d{2})", re.IGNORECASE)
_UNSUPPORTED_WINDOW = re.compile(
    r"\b(yesterday|last\s+\d+|past\s+\d+|earlier today|this morning)\b",
    re.IGNORECASE,
)


def _norm_hhmm(value: str) -> str:
    hours, minutes = value.split(":")
    return f"{int(hours):02d}:{int(minutes):02d}"


_TIME_FILTER_WITHOUT_HHMM = re.compile(
    r"\b(?:after|before|since|from)\s+(?:\d|last|past|yesterday|earlier)",
    re.IGNORECASE,
)


def _parse_timeline_window(text: str) -> dict[str, str] | None:
    """Return a supported HH:MM window, an unsupported error, or None."""
    after_match = _AFTER_TIME.search(text)
    before_match = _BEFORE_TIME.search(text)
    if after_match or before_match:
        window: dict[str, str] = {}
        if after_match:
            window["after"] = _norm_hhmm(after_match.group(1))
        if before_match:
            window["before"] = _norm_hhmm(before_match.group(1))
        return window
    if _UNSUPPORTED_WINDOW.search(text) or _TIME_FILTER_WITHOUT_HHMM.search(text):
        return {
            "error": (
                "This specialist filters timeline events with after/from/since "
                "or before HH:MM (24-hour). Other time windows are unsupported."
            )
        }
    return None


def _wants_slo_snapshot(text: str) -> bool:
    return _contains(
        text,
        "p99",
        "error budget",
        "error rate",
        "5xx",
        "slo",
        "latency",
        "snapshot",
    )


def _wants_additional_canary_only(text: str) -> bool:
    return _contains(text, "additional canary", "remaining canary") and not (
        _wants_slo_snapshot(text)
    )


def _is_postmortem_request(text: str) -> bool:
    return _contains(text, "postmortem", "post-mortem", "incident notes", "full notes")


def _is_metrics_request(text: str) -> bool:
    return _contains(
        text,
        "p99",
        "error budget",
        "error rate",
        "5xx",
        "slo",
        "canary percent",
        "latency",
        "snapshot",
        "additional canary",
    )


def _is_changelog_request(text: str) -> bool:
    return _contains(
        text,
        "changelog",
        "release notes",
        "2.4.1 change",
        "high-risk",
        "high risk",
        "next page",
        "reset the filter",
        "reset filter",
        "list all",
    )


def _is_risk_request(text: str) -> bool:
    return _contains(
        text,
        "go/no-go",
        "go or no-go",
        "hold or ship",
        "hold/ship",
        "release risk",
        "risk call",
        "ship the",
        "recommend hold",
        "should we hold",
    )


def _is_unsupported_press_work(text: str) -> bool:
    """Legal, payroll, or policy documents are not customer-status drafts."""
    if _contains(
        text,
        "status",
        "customer",
        "wording",
        "press",
        "comms",
        "communication",
    ):
        return False
    return _contains(
        text,
        "contract",
        "payroll",
        "tax filing",
        "refund",
        "legal document",
        "clause review",
    )


def _is_status_request(text: str) -> bool:
    if _is_unsupported_press_work(text):
        return False
    return _contains(
        text,
        "status",
        "customer",
        "wording",
        "press",
        "comms",
        "communication",
    )


def _resets_changelog_filter(text: str) -> bool:
    return _contains(
        text,
        "reset the filter",
        "reset filter",
        "clear the filter",
        "list all",
        "all 2.4.1",
        "unfiltered",
        "without the high-risk",
        "without the high risk",
    )


def _wants_high_risk(text: str) -> bool:
    return _contains(text, "high-risk", "high risk", "only the high")


def _wants_next_changelog_page(text: str) -> bool:
    return _contains(text, "next page", "page 2", "page 3", "another page")


_ROLLBACK_DENIED = re.compile(
    r"(?:do\s+not|don't|does\s+not|without|unless|not\s+a\s+|not\s+an\s+|"
    r"has\s+not|have\s+not|not\s+been|not\s+claim|not\s+treat|not\s+confirmation)"
    r".{0,80}(?:rollback|roll[\s-]?back|rolled\s+back)"
    r"|"
    r"(?:rollback|roll[\s-]?back|rolled\s+back).{0,80}"
    r"(?:unless|is\s+not\s+execution|not\s+confirmation|not\s+confirmed|wording\s+only)",
    re.IGNORECASE | re.DOTALL,
)


def _is_negated_rollback(text: str) -> bool:
    if _contains(
        text,
        "do not rollback",
        "don't rollback",
        "do not roll back",
        "don't roll back",
        "not rolling back",
        "without rollback",
        "no rollback",
        "has not been rolled back",
        "have not been rolled back",
        "not a confirmed rollback",
    ):
        return True
    return _ROLLBACK_DENIED.search(text) is not None


def _is_prepare_rollback(text: str) -> bool:
    if _contains(
        text,
        "prepare rollback",
        "rollback wording",
        "prepare a rollback",
        "draft rollback",
        "rollback language",
        "prepare the rollback",
        "wording only",
        "not execution",
    ):
        return True
    lowered = text.lower()
    preparing = any(word in lowered for word in ("prepare", "preparing", "preparation"))
    rollback = "rollback" in lowered or "roll back" in lowered
    return preparing and rollback and not _is_negated_rollback(text)


def _is_confirmed_rollback(text: str) -> bool:
    if _is_negated_rollback(text):
        return False
    return _contains(
        text,
        "has been rolled back",
        "have been rolled back",
        "rollback is complete",
        "rollback complete",
        "confirmed rollback",
        "rollback confirmed",
        "rolled back to",
        "canary rolled back",
    )


def _is_hold_language(text: str) -> bool:
    return _contains(text, "legal", "hold language", "do not expand", "will not expand")


_PRESS_HOLD = (
    "Checkout is slower than usual for some payments-api customers "
    "on canary 2.4.1. We are holding the rollout."
)
_PRESS_LEGAL = (
    "Checkout is slower than usual for some payments-api customers "
    "on canary 2.4.1. Legal requires hold language: we are holding "
    "the rollout and will not expand the canary."
)
_PRESS_PREPARE = (
    "Checkout is slower than usual for some payments-api customers "
    "on canary 2.4.1. We are holding the rollout. Rollback wording is "
    "being prepared; the canary has not been rolled back."
)
_PRESS_REQUESTED = (
    "Checkout is slower than usual for some payments-api customers "
    "on canary 2.4.1. A rollback has been requested. We are holding "
    "the rollout; the canary has not been rolled back."
)
_PRESS_NEGATED = (
    "Checkout is slower than usual for some payments-api customers "
    "on canary 2.4.1. We are holding the rollout. The canary has not "
    "been rolled back."
)
_PRESS_CONFIRMED = (
    "Checkout is slower than usual for some payments-api customers "
    "on canary 2.4.1. The canary has been rolled back to 2.4.0."
)


def _press_status(notices: list[str]) -> str:
    """Map accepted notices to customer wording.

    Preparation, negation, or an instruction is not execution. Newest
    notice that names a status wins among confirmed, prepare, hold, and
    a plain rollback request.
    """
    blob = " ".join(notices)
    for notice in reversed(notices):
        if _is_negated_rollback(notice):
            return _PRESS_LEGAL if _is_hold_language(blob) else _PRESS_NEGATED
        if _is_confirmed_rollback(notice):
            return _PRESS_CONFIRMED
        if _is_prepare_rollback(notice):
            return _PRESS_LEGAL if _is_hold_language(blob) else _PRESS_PREPARE
        if _is_hold_language(notice):
            return _PRESS_LEGAL
        if _contains(notice, "rollback", "roll back"):
            return _PRESS_REQUESTED
    if _is_hold_language(blob):
        return _PRESS_LEGAL
    return _PRESS_HOLD


async def _await_ticket(getter: Any, ticket_id: str) -> Any:
    while True:
        ticket = await getter(ticket_id)
        if getattr(ticket, "state", None) != "open":
            return ticket
        await asyncio.sleep(0.05)


async def _finish_deferred(pending: Any, content: Any) -> None:
    try:
        await pending.reply(content)
    except asyncio.CancelledError:
        raise
    except (SessionError, RuntimeError):
        return


class _BackgroundWork:
    """Own delayed tasks and cancel them on leave."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._tasks: set[asyncio.Task[None]] = set()

    def _spawn(self, coro: Any) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _stop_background(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def leave(self) -> None:
        await self._stop_background()
        await super().leave()


class IncidentTriage(_BackgroundWork, BaseAgent):
    """Reconstructs the canary timeline and may ask peer specialists."""

    profile = AgentProfile(
        summary="Reconstructs payment-canary incidents and coordinates hold calls.",
        description=(
            "Use for payments-api 2.4.1 timeline reconstruction, delayed "
            "forensic traces, heap-dump symbol notes, open SEV0 lists by "
            "region, retained postmortem notes, and a hold recommendation "
            "that asks metrics-analyst and changelog-scribe. Timeline "
            "follow-ups may filter with after/from/since or before HH:MM; "
            "other time windows are refused. Mixed forensic plus hold in "
            "one request is declined. Lab notes reply generically so "
            "history parent_id identifies the request. Other work is declined."
        ),
        skills=[
            Skill(
                name="incident_timeline",
                description="Return the canary timeline for payments-api 2.4.1.",
                examples=[
                    "Reconstruct the payments-api 2.4.1 canary timeline.",
                    "List open SEV0 incidents in eu-west-3.",
                    "List timeline events after 14:18.",
                ],
                tags=["incident", "canary"],
            ),
            Skill(
                name="forensic_trace",
                description="Rebuild the same timeline from traces after a short delay.",
                examples=["Run a forensic reconstruction of INC-4821."],
                tags=["forensics"],
            ),
            Skill(
                name="hold_recommendation",
                description="Ask metrics and changelog peers, then recommend hold or ship.",
                examples=["Should we hold the payments-api 2.4.1 canary?"],
                tags=["release"],
            ),
            Skill(
                name="incident_postmortem",
                description="Return the retained INC-4821 postmortem notes.",
                examples=["Give the INC-4821 postmortem notes."],
                tags=["incident", "notes"],
            ),
            Skill(
                name="lab_note",
                description="Record a lab observation. Replies are generic.",
                examples=["Record this lab observation as a lab note."],
                tags=["incident", "notes"],
            ),
        ],
        tags=["incident", "payments", "canary"],
    )

    def __init__(self) -> None:
        super().__init__(name="incident-triage", max_in_flight=4)
        self._next_lab_note_delay = LAB_NOTE_SLOW_SECONDS

    async def handle(self, msg: MailboxMessage, ctx: Context) -> Any:
        if msg.kind != "request":
            return None
        text = _as_text(msg.content)
        hold = _is_hold_request(text)
        forensic = _is_forensic_request(text)
        if hold and forensic:
            return None
        if _asks_prior_identifier(text):
            prior = _prior_incident_id(ctx)
            if prior is None:
                return {"incident_id": None, "source": "no_prior_turn"}
            return {"incident_id": prior, "source": "thread_history"}
        if _is_heap_request(text):
            pending = ctx.defer()
            self._spawn(self._finish_heap_dump(pending))
            return None
        if _is_lab_note_request(text):
            pending = ctx.defer()
            delay = self._next_lab_note_delay
            self._next_lab_note_delay = LAB_NOTE_FAST_SECONDS
            self._spawn(self._finish_lab_note(pending, delay))
            return None
        if forensic:
            pending = ctx.defer()
            self._spawn(self._finish_forensic(pending))
            return None
        if hold:
            return await self._recommend(ctx)
        if _is_postmortem_request(text):
            return {
                "incident_id": INCIDENT["incident_id"],
                "source": "postmortem",
                "notes": POSTMORTEM_NOTES,
            }
        if _is_sev0_request(text):
            blob = _request_blob(msg, ctx)
            region = "eu-west-3" if "eu-west-3" in blob else "us-east-1"
            return {
                "region": region,
                "open_sev0": list(INCIDENT["open_sev0_by_region"][region]),
            }
        if _is_timeline_request(text) or _parse_timeline_window(text) is not None:
            window = _parse_timeline_window(text)
            if window is None:
                window = _parse_timeline_window(_request_blob(msg, ctx))
            return self._timeline(
                include_remaining_health=_wants_remaining_health(text),
                window=window,
            )
        return None

    def _timeline(
        self,
        *,
        include_remaining_health: bool,
        window: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        events = list(INCIDENT["timeline"])
        if window is not None and window.get("error"):
            return {
                "incident_id": INCIDENT["incident_id"],
                "constraint": "unsupported",
                "reason": window["error"],
            }
        applied: str | None = None
        if window is not None:
            after = window.get("after")
            before = window.get("before")
            if after:
                events = [row for row in events if row["at"] >= after]
                applied = f"after {after}"
            if before:
                events = [row for row in events if row["at"] < before]
                applied = (
                    f"{applied} and before {before}" if applied else f"before {before}"
                )
        body: dict[str, Any] = {
            "incident_id": INCIDENT["incident_id"],
            "service": INCIDENT["service"],
            "release": INCIDENT["release"],
            "canary_percent": INCIDENT["canary_percent"],
            "timeline": events,
        }
        if applied:
            body["constraint"] = applied
        if include_remaining_health:
            body["follow_up"] = (
                "The remaining 90% of traffic stayed on 2.4.0 and was healthy."
            )
        return body

    async def _finish_lab_note(self, pending: Any, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            await _finish_deferred(pending, {"recorded": True})
        except asyncio.CancelledError:
            raise

    async def _finish_forensic(self, pending: Any) -> None:
        try:
            await asyncio.sleep(FORENSIC_DELAY_SECONDS)
            await _finish_deferred(
                pending,
                {
                    "incident_id": INCIDENT["incident_id"],
                    "source": "traces",
                    "span_id": "span-8f21",
                    "timeline": list(INCIDENT["timeline"]),
                },
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            try:
                await pending.fail("forensic reconstruction did not finish")
            except Exception:
                return

    async def _finish_heap_dump(self, pending: Any) -> None:
        try:
            await asyncio.sleep(HEAP_DUMP_DELAY_SECONDS)
            await _finish_deferred(
                pending,
                {
                    "incident_id": INCIDENT["incident_id"],
                    "symbols": ["checkout_handler", "idempotency_store"],
                },
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            try:
                await pending.fail("heap-dump notes did not finish")
            except Exception:
                return

    async def _recommend(self, ctx: Context) -> dict[str, Any] | None:
        metrics = await ctx.ask(
            "metrics-analyst",
            {"question": "error budget and p99 for the payments-api 2.4.1 canary"},
            collect="ticket",
        )
        notes = await ctx.ask(
            "changelog-scribe",
            {"question": "high-risk changes in payments-api 2.4.1"},
            collect="ticket",
        )
        if metrics.state == "completed" and notes.state == "completed":
            return self._hold_payload(metrics, notes)
        pending = ctx.defer()
        self._spawn(self._finish_recommend(pending, metrics.id, notes.id))
        return None

    async def _finish_recommend(
        self, pending: Any, metrics_id: str, notes_id: str
    ) -> None:
        try:
            metrics = await _await_ticket(self.get_result, metrics_id)
            notes = await _await_ticket(self.get_result, notes_id)
            await _finish_deferred(pending, self._hold_payload(metrics, notes))
        except asyncio.CancelledError:
            raise
        except Exception:
            try:
                await pending.fail("hold recommendation did not finish")
            except Exception:
                return

    def _hold_payload(self, metrics: Any, notes: Any) -> dict[str, Any]:
        if metrics.state != "completed" or notes.state != "completed":
            return {
                "status": "partial",
                "recommendation": "hold_canary",
                "reason": (
                    "Peer work did not complete a full snapshot; holding the "
                    "canary on the known checkout SLO breach."
                ),
                "metrics_state": metrics.state,
                "changelog_state": notes.state,
                "metrics": _ticket_content(metrics),
                "high_risk_changes": _ticket_content(notes),
            }
        return {
            "status": "ready",
            "recommendation": "hold_canary",
            "reason": (
                "p99 and 5xx exceeded SLO while the remaining 90% on 2.4.0 "
                "stayed healthy."
            ),
            "metrics": _ticket_content(metrics),
            "high_risk_changes": _ticket_content(notes),
        }


class MetricsAnalyst(_BackgroundWork, BaseAgent):
    """Returns SLO numbers, including valid zeros and empty lists."""

    profile = AgentProfile(
        summary="Reads checkout SLO telemetry for the payments-api canary.",
        description=(
            "Use for p99, 5xx rate, error budget, canary percent, and "
            "additional_canary_percent. Cannot decode heap dumps; that "
            "request fails. Other work is declined."
        ),
        skills=[
            Skill(
                name="slo_snapshot",
                description="Return p99, error rate, and remaining error budget.",
                examples=["What is p99 and error budget for payments-api 2.4.1?"],
                tags=["slo", "metrics"],
            ),
            Skill(
                name="canary_percent",
                description="Return current and additional canary percents.",
                examples=["What additional canary percent rolled after 10%?"],
                tags=["canary"],
            ),
        ],
        tags=["metrics", "slo", "payments"],
    )

    def __init__(self) -> None:
        super().__init__(name="metrics-analyst", max_in_flight=4)

    async def handle(self, msg: MailboxMessage, ctx: Context) -> Any:
        if msg.kind != "request":
            return None
        text = _as_text(msg.content)
        if _is_heap_request(text) or _contains(text, "pcap"):
            pending = ctx.defer()
            await pending.fail(
                "metrics-analyst cannot decode heap dumps or pcaps. "
                "Ask incident-triage."
            )
            return None
        if not _is_metrics_request(text):
            return None
        if _wants_additional_canary_only(text):
            payload = {
                "additional_canary_percent": METRICS["additional_canary_percent"]
            }
            return await self._maybe_delay(ctx, payload)
        payload = {
            "service": METRICS["service"],
            "release": METRICS["release"],
            "p99_ms": METRICS["p99_ms"],
            "baseline_p99_ms": METRICS["baseline_p99_ms"],
            "error_rate": METRICS["error_rate"],
            "slo_error_rate": METRICS["slo_error_rate"],
            "error_budget_remaining": METRICS["error_budget_remaining"],
            "canary_percent": METRICS["canary_percent"],
            "additional_canary_percent": METRICS["additional_canary_percent"],
        }
        return await self._maybe_delay(ctx, payload)

    def _nested_from_triage(self, ctx: Context) -> bool:
        return str(ctx.sender).startswith("incident-triage@")

    async def _maybe_delay(self, ctx: Context, payload: dict[str, Any]) -> Any:
        if not self._nested_from_triage(ctx) or NESTED_METRICS_DELAY_SECONDS <= 0:
            return payload
        pending = ctx.defer()
        self._spawn(self._finish_nested(pending, payload))
        return None

    async def _finish_nested(self, pending: Any, payload: dict[str, Any]) -> None:
        try:
            await asyncio.sleep(NESTED_METRICS_DELAY_SECONDS)
            await _finish_deferred(pending, payload)
        except asyncio.CancelledError:
            raise
        except Exception:
            try:
                await pending.fail("metrics snapshot did not finish")
            except Exception:
                return


class ChangelogScribe(BaseAgent):
    """Pages a compact 2.4.1 change list. Follow-ups stay on-thread."""

    profile = AgentProfile(
        summary="Lists payments-api 2.4.1 changes, including high-risk items.",
        description=(
            "Use for the 2.4.1 changelog. Ask again on the same Thread for "
            "the next page, high-risk items only, or an explicit filter reset "
            "to list all items. After a reset, next page continues the "
            "unfiltered list on that Thread. Other work is declined."
        ),
        skills=[
            Skill(
                name="release_notes",
                description="Return one page of 2.4.1 changes.",
                examples=[
                    "List payments-api 2.4.1 changelog items.",
                    "Only the high-risk 2.4.1 changes.",
                    "Reset the filter and list all 2.4.1 changes.",
                    "Next page of the changelog.",
                ],
                tags=["changelog", "release"],
            )
        ],
        tags=["changelog", "payments", "docs"],
    )

    def __init__(self) -> None:
        super().__init__(name="changelog-scribe", max_in_flight=4)

    async def handle(self, msg: MailboxMessage, ctx: Context) -> Any:
        if msg.kind != "request":
            return None
        text = _as_text(msg.content)
        if not _is_changelog_request(text):
            return None
        high = _changelog_high_filter(text, ctx)
        restart = _resets_changelog_filter(text) or (
            _wants_high_risk(text) and not _wants_next_changelog_page(text)
        )
        items = [row for row in CHANGELOG if (row["risk"] == "high" if high else True)]
        page = 0 if restart else _changelog_pages_sent(ctx, high=high)
        start = page * CHANGELOG_PAGE_SIZE
        chunk = items[start : start + CHANGELOG_PAGE_SIZE]
        has_more = start + CHANGELOG_PAGE_SIZE < len(items)
        return {
            "version": "2.4.1",
            "filter": "high" if high else "all",
            "page": page + 1,
            "changes": chunk,
            "has_more": has_more,
        }


def _changelog_high_filter(text: str, ctx: Context) -> bool:
    if _resets_changelog_filter(text):
        return False
    if _wants_high_risk(text):
        return True
    if _wants_next_changelog_page(text):
        for item in reversed(list(ctx.history)):
            content = getattr(item, "content", None)
            if isinstance(content, dict) and content.get("version") == "2.4.1":
                return content.get("filter") == "high"
    return False


def _changelog_pages_sent(ctx: Context, *, high: bool) -> int:
    """Count trailing pages of the current filter.

    An explicit reset or a filter switch starts a new paging segment.
    Same-filter reset must not keep counting older pages.
    """
    count = 0
    for item in reversed(list(ctx.history)):
        if _kind(item) == "request":
            if _resets_changelog_filter(_item_text(item)):
                break
            continue
        if _kind(item) != "response":
            continue
        content = getattr(item, "content", None)
        if not isinstance(content, dict) or content.get("version") != "2.4.1":
            continue
        if (content.get("filter") == "high") != high:
            break
        if "page" in content:
            count += 1
    return count


class RiskReviewer(BaseAgent):
    """Turns SLO and change facts into a hold/ship call."""

    profile = AgentProfile(
        summary="Makes a hold or ship call for overlapping payment-release risk.",
        description=(
            "Use after metrics and changelog notes exist. Overlaps with "
            "incident-triage on go/no-go language. Other work is declined."
        ),
        skills=[
            Skill(
                name="release_risk",
                description="Recommend hold or ship from supplied SLO and change facts.",
                examples=["Give a go/no-go for the payments-api 2.4.1 canary."],
                tags=["risk", "release"],
            )
        ],
        tags=["risk", "payments", "release"],
    )

    def __init__(self) -> None:
        super().__init__(name="risk-reviewer", max_in_flight=4)

    async def handle(self, msg: MailboxMessage, ctx: Context) -> Any:
        if msg.kind != "request":
            return None
        text = _as_text(msg.content)
        if not _is_risk_request(text):
            return None
        blob = _request_blob(msg, ctx)
        if _contains(blob, "940", "4.1", "0.041", "error budget", "p99"):
            return {
                "call": "hold",
                "until": "p99 and 5xx return to SLO",
                "note": "High-risk checkout changes shipped in the 10% canary.",
                "source": "fixture_rule",
            }
        return {
            "call": "need_facts",
            "need": "p99, error rate, and high-risk 2.4.1 changes",
            "source": "fixture_rule",
        }


class PressLiaison(_BackgroundWork, BaseAgent):
    """Drafts customer status. Later drafts include earlier tell notices."""

    profile = AgentProfile(
        summary="Drafts customer status for the payments canary.",
        description=(
            "Use for external wording. Notices sent with tell are included "
            "in a later status draft after they are processed. Accepted tell "
            "means queued, not processed. Include a needed fact in the ask "
            "when later wording depends on it. Legal hold language means "
            "the canary will not expand. A confirmed rollback notice may "
            "say the canary has been rolled back. Preparing or rejecting "
            "rollback wording is not execution. Other work is declined."
        ),
        skills=[
            Skill(
                name="status_draft",
                description="Write a short customer status from known canary facts.",
                examples=["Draft customer status for the payments-api canary."],
                tags=["comms", "status"],
            )
        ],
        tags=["comms", "press", "payments"],
    )

    def __init__(self) -> None:
        super().__init__(name="press-liaison", max_in_flight=4)
        self._notices: list[str] = []

    async def handle(self, msg: MailboxMessage, ctx: Context) -> Any:
        if msg.kind == "event":
            notice = _as_text(msg.content).strip()
            if notice:
                self._spawn(self._ingest_notice(notice))
            return None
        if msg.kind != "request":
            return None
        text = _as_text(msg.content)
        if _is_unsupported_press_work(text) or not _is_status_request(text):
            return None
        notices = list(self._notices)
        notices.extend(_event_notices(ctx))
        ask_text = text.strip()
        if ask_text:
            notices.append(ask_text)
        unique = list(dict.fromkeys(notices))
        draft = {
            "audience": "customers",
            "status": _press_status(unique),
            "source": "press-liaison",
        }
        if unique:
            draft["notices_incorporated"] = unique
        return draft

    async def _ingest_notice(self, notice: str) -> None:
        await asyncio.sleep(PRESS_NOTICE_DELAY_SECONDS)
        self._notices.append(notice)


TEAMMATES = (
    IncidentTriage,
    MetricsAnalyst,
    ChangelogScribe,
    RiskReviewer,
    PressLiaison,
)
