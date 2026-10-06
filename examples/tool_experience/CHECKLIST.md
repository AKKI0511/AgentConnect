# Ship-desk coverage checklist

Use this only after the uncoached hold-or-ship assignment. Do not follow
a prescribed tool sequence. Cover these through your own calls, then
update the same report.

- Discover teammates and pick recipients yourself, including one
  unfamiliar but suitable task and one unsupported task.
- Read several overlapping Profiles in one `get_profiles` call. Also
  try one address, a duplicate list, and a mix of valid and missing
  addresses. Do not call `get_profile`.
- Get a quick answer and a delayed answer.
- Keep more than one request outstanding on the same conversation, and
  on two independent conversations with the same specialist. Let replies
  finish out of order. Pair each reply using history `parent_id` (same
  value as that ask's `ticket_id`), including across a history page
  boundary. Generic lab-note replies do not name their request in
  content.
- Let a specialist ask a peer.
- Continue a conversation so earlier turns supply a constraint or fact.
  Do not assume a later reply applied a constraint unless the reply
  shows it.
- Send `content` as a bare string at least once.
- Cover delayed nested work (a specialist collecting a slow peer).
- See completed, declined, failed, and expired outcomes.
- See a valid empty list and a valid zero.
- Recover from ordinary tool errors (bad recipient, missing argument,
  a notice sent on someone else's conversation).
- Ask for work a specialist does not do; expect a refusal rather than a
  default document. Include a legal-contract or payroll ask to
  press-liaison.
- Ask one specialist for mixed work they cannot do together.
- After a changelog filter, explicitly reset it and confirm the later
  list is unfiltered. On that same conversation, ask for the next page
  and record whether remaining unfiltered items return. Also page two
  unfiltered lists, reset that same filter, then ask for the next page
  and record the page number and items.
- Ask metrics for p99, 5xx or error budget, and additional canary
  percent in one request. Record whether the SLO snapshot (including
  the zero) returns, rather than the zero alone.
- Continue an incident timeline conversation with after/from/since or
  before HH:MM. Record whether the constraint is applied or explicitly
  refused. Also try an unsupported window such as yesterday.
- Repeat an identical retryable request; then change content under the
  same retry key. Record the readable conflict text.
- Send a notice that a later relevant reply should reflect. Compare
  wording before and after. `tell` `accepted` means queued, not
  processed. Do not treat a parallel or immediate ask as proof the
  notice was ingested. If later wording depends on the notice, include
  the fact in that ask or ask for acknowledgement. Include a notice
  that only prepares or negates rollback, then one that confirms
  rollback. Preparation or negation must not claim the canary was
  rolled back.
- Request the longer incident notes and record returned size.
- Continue one conversation far enough to page history. Record page
  sizes and whether the returned cursor continues the same Thread.
- Record serialized result sizes (characters or bytes) for find cards,
  one `get_profiles` of several selected agents versus those Profiles
  fetched one at a time, tell, open and terminal TicketViews, a history
  page that includes `parent_id`, and tool-definition text if the
  catalog shows it. Note token counts if the harness shows them;
  otherwise write unknown. Record call counts, not only one response
  size.
- Confirm find has no detail argument, `get_profiles` has no DID and
  takes `addresses`, tell has no Message envelope, response history
  turns have `parent_id`, and completed TicketViews have no ttl_ms,
  deadline, or status_message.
- Pending work is not a terminal failure. A wait may return an open
  saved result; collect that same id. Ending the wait does not cancel
  work.
- For expiry, try a short deadline on work a Profile describes as slow.
  Read a completed saved request result after its original deadline.
