/**
 * AgentConnect public structures.
 *
 * This file is the structural source of truth. The surrounding Markdown owns
 * behavior and state transitions. Generate schema.json with `npm run generate`.
 *
 * Only data that crosses a Runtime boundary belongs here. Runtime storage,
 * Agent implementation objects, and transport internals do not.
 *
 * Stability: this is a pre-1.0 draft. Any part of it may change without a
 * compatibility guarantee until the contract freezes at 1.0. A Runtime and its
 * Clients ship together and must implement the same draft.
 */

/** Exact AgentConnect specification version. */
export type SpecVersion = "1.0.0-draft";

/**
 * UTC RFC 3339 timestamp with a trailing `Z`.
 * Example: `2026-08-18T15:00:00Z`.
 * @format date-time
 * @pattern ^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$
 */
export type Timestamp = string;

/**
 * RFC 9562 UUID used for Messages, Threads, leases, traces, and Instances.
 * @format uuid
 */
export type Uuid = string;

/**
 * Agent name input. Length 1 to 63. The Runtime canonicalizes ASCII uppercase
 * to lowercase; `-` and `_` are allowed only between alphanumeric characters.
 * @pattern ^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9])?$
 */
export type AgentName = string;

/**
 * Lowercase Team name and valid DNS label. Length 1 to 63.
 * @pattern ^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$
 */
export type TeamName = string;

/**
 * Agent Address accepted by the grammar in addressing.md. The location, when
 * present, is one or more dot-separated DNS labels. The Runtime canonicalizes
 * ASCII uppercase to lowercase.
 * Examples: `writer`, `writer@content-squad`, `writer@legal.acme.com`.
 * @maxLength 317
 * @pattern ^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9])?(?:@(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*)?$
 */
export type Address = string;

/**
 * Canonical Address stored in Runtime-owned output. Both parts are lowercase
 * and the location is always present. The location is one or more
 * dot-separated DNS labels, so this type already represents a remote Address
 * such as `writer@legal.acme.com`. A single-Team Runtime only ever emits a
 * single-label location equal to its own Team name.
 * @maxLength 317
 * @pattern ^[a-z0-9](?:[a-z0-9_-]{0,61}[a-z0-9])?@(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$
 */
export type QualifiedAddress = string;

/**
 * Agent-owned `did:key` identity backed by an Ed25519 public key.
 * @format uri
 * @pattern ^did:key:z[1-9A-HJ-NP-Za-km-z]+$
 */
export type AgentDid = string;

/**
 * Opaque non-empty bearer credential returned by join.
 * @minLength 1
 */
export type SessionToken = string;

/** Any value representable in JSON. */
export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

/** JSON object with application-defined keys. */
export type JsonObject = { [key: string]: JsonValue };

/** How a Runtime survives process exit. */
export type PersistenceMode = "volatile" | "durable";

/**
 * How the sender collects the result of a request. It is a choice made on
 * the `send` call and is not stored on the immutable Message; the recipient
 * never observes it. Every request carries `collect` and a `deadline` and
 * opens a Ticket. An event is the fire-and-forget kind and names neither.
 *
 * - `wait`: keep `send` open until the Ticket is terminal or `wait_hold_seconds` elapses, then return the current Ticket.
 * - `ticket`: return a Ticket immediately and collect the result later.
 * - `callback`: return immediately and deliver the result to a target later.
 * - `stream`: receive partial results ending with a final result.
 *
 * The current draft implements `wait` and `ticket`. `callback` and `stream`
 * are named so their contract is fixed, and a `send` that requests them fails
 * with `unsupported_collect_mode` until they are implemented.
 */
export type CollectMode = "wait" | "ticket" | "callback" | "stream";

/** Closed set of Ticket states. */
export type TicketState =
  | "open"
  | "completed"
  | "failed"
  | "expired"
  | "declined";

/**
 * Well-known public error codes. `ErrorObject.code` is this closed set. An
 * Agent application failure code belongs in `ErrorObject.details`.
 */
export type ErrorCode =
  | "unsupported_version"
  | "unsupported_collect_mode"
  | "unauthorized"
  | "forbidden"
  | "invalid_request"
  | "invalid_address"
  | "address_outside_team"
  | "not_found"
  | "name_conflict"
  | "id_conflict"
  | "busy"
  | "payload_too_large"
  | "lease_expired"
  | "ticket_closed"
  | "unavailable"
  | "internal"
  | "handler_failed"
  | "deadline_exceeded";

/**
 * Lowercase discovery label.
 * @pattern ^[a-z0-9](?:[a-z0-9_-]{0,30}[a-z0-9])?$
 */
export type Tag = string;

/**
 * Short natural-language example of using a Skill. Examples are illustrative
 * text, not typed contracts, because a request to an Agent is free-form
 * `content`, not a call against a declared signature.
 * @minLength 1
 * @maxLength 500
 * @pattern \S
 */
export type SkillExample = string;

/**
 * One thing an Agent claims it can do, described in natural language.
 *
 * A Skill has no input or output schema. An Agent is addressed as one
 * conversational participant; a caller describes the work in `content` and does
 * not target a typed Skill signature. Skills exist to make discovery specific
 * and to render an Agent's abilities to a reader, not to define an RPC surface.
 */
export interface Skill {
  /**
   * Stable lowercase identifier, unique within the Profile. It is not an
   * Address or a Runtime operation name.
   * @pattern ^[a-z0-9](?:[a-z0-9_-]{0,61}[a-z0-9])?$
   */
  name: string;
  /**
   * Direct description of what the Skill does.
   * @minLength 1
   * @maxLength 1000
   * @pattern \S
   */
  description: string;
  /**
   * Concrete natural-language examples used for discovery and reader
   * understanding.
   * @maxItems 10
   */
  examples?: SkillExample[];
  /**
   * Optional lowercase labels scoped to this Skill.
   * @maxItems 20
   * @uniqueItems true
   */
  tags?: Tag[];
}

/**
 * Discovery information for an Agent.
 *
 * A Profile describes what one participant can do, the way a short bio
 * describes a person. Identity, name, Address, presence, and Session data do
 * not belong here; the DirectoryEntry owns identity and addressing.
 */
export interface AgentProfile {
  /**
   * Short description used in discovery results.
   * @minLength 1
   * @maxLength 200
   * @pattern \S
   */
  summary: string;
  /**
   * Longer optional explanation of suitable work and boundaries.
   * @minLength 1
   * @maxLength 2000
   * @pattern \S
   */
  description?: string;
  /**
   * One or more Skills. Names must be unique within this array.
   * @minItems 1
   * @maxItems 50
   */
  skills: Skill[];
  /**
   * Lowercase discovery labels. Duplicate tags are invalid.
   * @maxItems 20
   * @uniqueItems true
   */
  tags?: Tag[];
}

/**
 * Public failure data. Runtime errors and Agent handler failures share this
 * shape so Clients can handle them consistently.
 */
export interface ErrorObject {
  /**
   * Well-known ErrorCode. An Agent application failure code belongs in
   * `details` of a `handler_failed` error, whose shape the Agent owns.
   */
  code: ErrorCode;
  /**
   * Safe human-readable explanation.
   * @minLength 1
   * @maxLength 2000
   * @pattern \S
   */
  message: string;
  /** Optional structured data safe to reveal to the requester. */
  details?: JsonObject;
  /** Whether repeating the failed action may succeed without changing input. */
  retryable?: boolean;
}

/** Error stored by an expired Ticket. */
export interface DeadlineExceededError extends ErrorObject {
  /** Fixed code for deadline expiry. */
  code: "deadline_exceeded";
}

/**
 * Fields shared by every accepted Message. The Runtime sets the Message `id`
 * (acceptance is keyed on it), the canonical Addresses, `created_at`,
 * `trace_id`, and `seq` when `thread_id` is present. A Client cannot set the
 * Runtime-owned fields.
 */
export interface MessageBase {
  /** Immutable Message id and idempotency key. */
  id: Uuid;
  /** Canonical qualified Address set by the Runtime. */
  sender: QualifiedAddress;
  /** Canonical qualified Address set by the Runtime. */
  recipient: QualifiedAddress;
  /** Runtime acceptance time. */
  created_at: Timestamp;
  /**
   * Correlation id shared by every Message in one causal exchange. The Runtime
   * assigns a new value to a root Message and copies it onto every Message
   * caused by it, so one `trace_id` reconstructs a whole timeline.
   */
  trace_id: Uuid;
  /** Optional Thread grouping id. */
  thread_id?: Uuid;
  /**
   * Message this one replies to or continues. Singular: the Message relation
   * is a tree. A response or error MUST name the request. A follow-up request
   * or event MAY name a prior Message in the same Thread. A result merged
   * from several answers names one parent and records the other inputs
   * through the shared `trace_id`.
   */
  parent_id?: Uuid;
  /**
   * Position of this Message in its Thread, assigned on acceptance. Present
   * exactly when `thread_id` is present. The first accepted Message in a
   * Thread is `1`. Each later Message, including a response or error,
   * receives the next integer. History, the delivered window, and `before`
   * cursors order by this value, not by `created_at`.
   * @minimum 1
   * @multipleOf 1
   */
  seq?: number;
}

/**
 * Request that always expects a reply. It carries a `deadline`, opens a
 * Ticket, and ends in a terminal Ticket state. Fire-and-forget work is an
 * `event`.
 */
export interface RequestMessage extends MessageBase {
  /** Identifies work sent to an Agent. */
  kind: "request";
  /** Sender-controlled work input. */
  content: JsonValue;
  /** Sender-controlled application data. Never used for Runtime decisions. */
  metadata?: JsonObject;
  /** Absolute time after which an open Ticket expires. */
  deadline: Timestamp;
}

/** Information sent without a reply or Ticket. */
export interface EventMessage extends MessageBase {
  /** Identifies information sent without a Ticket. */
  kind: "event";
  /** Sender-controlled event data. */
  content: JsonValue;
  /** Sender-controlled application data. Never used for Runtime decisions. */
  metadata?: JsonObject;
}

/** Message kind stored in a Membership Mailbox and eligible for Delivery. */
export type MailboxMessage = RequestMessage | EventMessage;

/** Successful reply created by the Runtime. */
export interface ResponseMessage extends MessageBase {
  /** Identifies a successful reply. */
  kind: "response";
  /** Successful application result. May be null when the Agent returns none. */
  content: JsonValue;
  /** Request Message id. */
  parent_id: Uuid;
}

/** Failed reply created by the Runtime. */
export interface ErrorMessage extends MessageBase {
  /** Identifies a failed reply. */
  kind: "error";
  /** Safe failure returned to the requester. */
  error: ErrorObject;
  /** Request Message id. */
  parent_id: Uuid;
}

/** Immutable Message stored by the Runtime. */
export type Message =
  | RequestMessage
  | EventMessage
  | ResponseMessage
  | ErrorMessage;

/**
 * One exclusive attempt to handle a Message.
 *
 * `history` is a bounded recent window of the Thread, ordered by `seq`
 * ascending and excluding `message`. The window is capped by
 * `delivery_history_limit` and by `max_message_bytes`. When
 * `history_complete` is false, older retained Messages exist and can be paged
 * with `get_history`. This keeps a Delivery's size bounded no matter how long
 * a Thread grows.
 */
export interface Delivery {
  /** Opaque id authorizing completion of this attempt. */
  lease_id: Uuid;
  /** Time after which this attempt is no longer active. */
  lease_expires_at: Timestamp;
  /**
   * Starts at 1 and increases after recovery.
   * @minimum 1
   * @multipleOf 1
   */
  attempt: number;
  /** Request or event leased from the Membership's Mailbox. */
  message: MailboxMessage;
  /** Bounded recent window of earlier Messages from this Thread. */
  history: Message[];
  /** True when `history` already contains every earlier retained Message. */
  history_complete: boolean;
}

/** Fields shared by every Ticket state. */
export interface TicketBase {
  /** Request Message id. */
  id: Uuid;
  /** Membership that sent the request and owns this Ticket. */
  requester: QualifiedAddress;
  /** Membership asked to handle the request. */
  recipient: QualifiedAddress;
  /**
   * Thread the request belongs to, when it has one. Kept on the Ticket so the
   * requester can continue the conversation from the result alone. The
   * request's `trace_id` is not repeated here; it is a Message field, read
   * from the request or the stored response.
   */
  thread_id?: Uuid;
  /** Request acceptance time. */
  created_at: Timestamp;
  /** Time of the last state transition or late-reply observation. */
  updated_at: Timestamp;
  /** Absolute time after which an open Ticket expires. */
  deadline: Timestamp;
  /**
   * Number of distinct replies observed after this Ticket became terminal.
   * @minimum 0
   * @multipleOf 1
   */
  late_reply_count: number;
}

/** Ticket waiting for its first accepted reply. */
export interface OpenTicket extends TicketBase {
  /** Ticket still waiting for its first accepted outcome. */
  state: "open";
}

/** Ticket completed by one successful response. */
export interface CompletedTicket extends TicketBase {
  /** Ticket closed by a successful reply. */
  state: "completed";
  /** Immutable winning response. */
  response: ResponseMessage;
}

/** Ticket completed by an Agent or Runtime failure. */
export interface FailedTicket extends TicketBase {
  /** Ticket closed by an Agent failure. */
  state: "failed";
  /** Immutable winning failure. */
  error: ErrorObject;
}

/** Ticket whose deadline passed before an accepted reply. */
export interface ExpiredTicket extends TicketBase {
  /** Ticket closed because its deadline passed first. */
  state: "expired";
  /** Fixed deadline failure. */
  error: DeadlineExceededError;
}

/**
 * Ticket the recipient deliberately declined. The recipient handled the
 * request and chose not to answer, the way a person may read a message and
 * decide no reply is warranted. It is a terminal, non-failure outcome that is
 * explicit to the requester, distinct from a handler failure and from a
 * deadline that expired with no handling.
 */
export interface DeclinedTicket extends TicketBase {
  /** Ticket closed because the recipient chose not to respond. */
  state: "declined";
}

/** Requester-owned durable result record. */
export type Ticket =
  | OpenTicket
  | CompletedTicket
  | FailedTicket
  | ExpiredTicket
  | DeclinedTicket;

/** Full Directory record for one Membership, returned by `get_profile`. */
export interface DirectoryEntry {
  /** Canonical qualified Address. */
  address: QualifiedAddress;
  /** Stable identity supplied by the Membership. */
  agent_did: AgentDid;
  /** Current discovery information. */
  profile: AgentProfile;
}

/**
 * One ranked discovery result. It is light by default so a search can list a
 * whole Team without flooding a model's context. `agent_did` and `profile` are
 * present only when the search requested full detail.
 */
export interface DirectoryMatch {
  /** Canonical qualified Address to send work to. */
  address: QualifiedAddress;
  /** Profile summary line. */
  summary: string;
  /** Declared Skill names, for a cheap capability scan. */
  skill_names: string[];
  /** Optional discovery labels. */
  tags?: Tag[];
  /** Stable identity. Present only when detail is `full`. */
  agent_did?: AgentDid;
  /** Full discovery information. Present only when detail is `full`. */
  profile?: AgentProfile;
}

/** Short-lived challenge used to prove Agent DID control. */
export interface JoinChallenge {
  /**
   * At least 128 bits of random data in base64url form.
   * @pattern ^[A-Za-z0-9_-]{22,64}$
   */
  nonce: string;
  /**
   * Exact JWT audience required by the Runtime.
   * @pattern ^agentconnect:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$
   */
  audience: string;
  /** Time after which this challenge cannot authenticate a join. */
  expires_at: Timestamp;
}

/** Input that creates or reconnects a Membership and opens one Instance. */
export interface JoinRequest {
  /** Exact public contract version implemented by the Client. */
  spec_version: SpecVersion;
  /** Requested Agent name, canonicalized by the Runtime. */
  name: AgentName;
  /** Agent-owned identity proved by `identity_proof`. */
  agent_did: AgentDid;
  /** Discovery information that replaces the Membership's current Profile. */
  profile: AgentProfile;
  /**
   * Stable id for one running copy of the Agent. It MUST be unique per running
   * copy. Re-joining with the same `instance_id` replaces that Instance's
   * Session; a different value opens an additional concurrent Instance sharing
   * the Membership and Mailbox. Omit to let the Runtime assign one.
   */
  instance_id?: Uuid;
  /**
   * Maximum active Delivery leases for this Session. Defaults to 1.
   * @minimum 1
   * @maximum 100
   * @multipleOf 1
   */
  max_in_flight?: number;
  /**
   * Required by a network Runtime; omitted for trusted embedded join.
   * @minLength 1
   */
  join_token?: string;
  /**
   * EdDSA JWT required by a network Runtime.
   * @minLength 1
   */
  identity_proof?: string;
}

/** Fixed operational limits a Runtime reports at join. */
export interface RuntimeLimits {
  /**
   * Maximum accepted size in bytes of a `send` body's UTF-8 JSON encoding.
   * A larger `send` fails with `payload_too_large`. The same budget caps a
   * Delivery `history` window: the window's UTF-8 JSON encoding MUST NOT
   * exceed this value.
   * @minimum 1
   * @multipleOf 1
   */
  max_message_bytes: number;
  /**
   * Maximum Messages one Membership Mailbox holds before `send` returns busy.
   * @minimum 1
   * @multipleOf 1
   */
  max_mailbox_depth: number;
  /**
   * Maximum earlier Thread Messages the Runtime includes in a Delivery's
   * `history` window. Older Messages are paged with `get_history`. The window
   * is also truncated so its UTF-8 JSON encoding does not exceed
   * `max_message_bytes`.
   * @minimum 0
   * @multipleOf 1
   */
  delivery_history_limit: number;
  /**
   * Seconds a `collect=wait` `send` may stay open. When this elapses and the
   * Ticket is still `open`, `send` returns that Ticket and the Client
   * continues with `get_result`. `0` returns immediately after acceptance.
   * @minimum 0
   */
  wait_hold_seconds: number;
}

/** Result of a successful join. */
export interface JoinResult {
  /** Bearer credential for the new Session. */
  session_token: SessionToken;
  /** Current Session expiry. */
  session_expires_at: Timestamp;
  /** Canonical qualified Address assigned to the Membership. */
  address: QualifiedAddress;
  /** Canonical name of the Team served by this Runtime. */
  team_name: TeamName;
  /** Verified identity bound to the Membership. */
  agent_did: AgentDid;
  /** Instance id for this Session, assigned when the Client omitted one. */
  instance_id: Uuid;
  /** Runtime restart guarantee. */
  persistence: PersistenceMode;
  /** Operational limits this Runtime enforces. */
  limits: RuntimeLimits;
  /** Exact public contract version implemented by the Runtime. */
  spec_version: SpecVersion;
}

/** Result of a successful Session heartbeat. */
export interface HeartbeatResult {
  /** Current Session expiry after the heartbeat. */
  session_expires_at: Timestamp;
}

/** Fields shared by request and event sends. */
export interface SendBase {
  /** Client-generated Message id and idempotency key. */
  id: Uuid;
  /** Local or same-Team qualified Address. */
  recipient: Address;
  /** Sender-controlled work or event data. */
  content: JsonValue;
  /** Optional conversation grouping id. */
  thread_id?: Uuid;
  /** Optional Message this send replies to or continues. */
  parent_id?: Uuid;
  /** Sender-controlled data that never changes Runtime decisions. */
  metadata?: JsonObject;
}

/** Target that receives a `callback` result. Reserved until callback lands. */
export type CallbackTarget =
  | {
      /** Local or same-Team Address that receives the result as a Message. */
      address: Address;
    }
  | {
      /**
       * Absolute HTTPS URL the Runtime POSTs the result to.
       * @format uri
       */
      url: string;
    };

/**
 * Send a request. Always opens a Ticket. `collect` and `deadline` are
 * required. Fire-and-forget work is `EventSendRequest`.
 */
export interface RequestSendRequest extends SendBase {
  /** Send work to be handled. */
  kind: "request";
  /** How the sender collects the result. */
  collect: CollectMode;
  /** Future absolute deadline for the Ticket. */
  deadline: Timestamp;
  /** Required only when `collect` is `callback`. */
  callback?: CallbackTarget;
}

/** Send information without a reply. */
export interface EventSendRequest extends SendBase {
  /** Send information without a Ticket. */
  kind: "event";
}

/** Input to Runtime `send`. */
export type SendRequest = RequestSendRequest | EventSendRequest;

/** Result for an event. */
export interface AcceptedSendResult {
  /** Discriminator for a send that created no Ticket. */
  status: "accepted";
  /** Accepted and Runtime-stamped event. */
  message: EventMessage;
}

/** Result for a request. */
export interface TicketedSendResult {
  /** Discriminator for a request send. */
  status: "ticketed";
  /** Accepted and Runtime-stamped request. */
  message: RequestMessage;
  /** Current Ticket. Terminal unless `collect=wait` ended at the wait hold. */
  ticket: Ticket;
}

/** Result of Runtime `send`. */
export type SendResult = AcceptedSendResult | TicketedSendResult;

/** Input to pull available work. */
export interface LeaseRequest {
  /**
   * Number requested, from 1 to 100. Defaults to 1.
   * @minimum 1
   * @maximum 100
   * @multipleOf 1
   */
  max_items?: number;
}

/** Deliveries currently leased to the Session. */
export interface LeaseResult {
  /** Zero or more newly leased attempts. */
  deliveries: Delivery[];
}

/**
 * Finish one Delivery without a response. For an event this just ends the
 * Delivery. For a request it declines the request: the recipient chose not
 * to answer, and the Ticket becomes `declined`.
 */
export interface CompleteRequest {
  /** Active lease to finish. */
  lease_id: Uuid;
}

/** Result of `complete`. */
export interface CompleteResult {
  /** Present only when completing a request, which declines it. */
  ticket?: DeclinedTicket;
}

/** Fields shared by successful and failed replies. */
export interface ReplyBase {
  /** Client-generated id for the response or error Message. */
  id: Uuid;
  /** Active lease for the reply-expected request. */
  lease_id: Uuid;
}

/** Complete a Delivery with successful content. */
export interface ReplySuccessRequest extends ReplyBase {
  /** Selects a successful Ticket transition. */
  outcome: "completed";
  /** Successful application result. Use null to answer with no content. */
  content: JsonValue;
}

/** Complete a Delivery with a safe error. */
export interface ReplyFailureRequest extends ReplyBase {
  /** Selects a failed Ticket transition. */
  outcome: "failed";
  /** Safe application or handler failure. */
  error: ErrorObject;
}

/** Input to Runtime `reply`. */
export type ReplyRequest = ReplySuccessRequest | ReplyFailureRequest;

/** Result of an accepted reply. */
export interface ReplyResult {
  /** Terminal Ticket containing the accepted outcome. */
  ticket: CompletedTicket | FailedTicket;
}

/** Ticket lookup used by non-HTTP bindings. */
export interface GetResultRequest {
  /** Ticket id, equal to its original request Message id. */
  ticket_id: Uuid;
}

/** Thread history lookup. */
export interface GetHistoryRequest {
  /** Thread whose retained Messages are read. */
  thread_id: Uuid;
  /**
   * Return Messages older than this Message id, exclusive. Omit for the newest
   * page. A well-formed UUID that is not in the retained transcript, including
   * an evicted id, returns the newest page. A non-UUID value is
   * `invalid_request`.
   */
  before?: Uuid;
  /**
   * Page size from 1 to 200. Defaults to 50.
   * @minimum 1
   * @maximum 200
   * @multipleOf 1
   */
  limit?: number;
}

/** One page of retained Thread history. */
export interface HistoryResult {
  /** Requested page ordered by `seq` ascending. */
  messages: Message[];
  /** True when older retained Messages remain before this page. */
  has_more: boolean;
}

/** Local Directory search input. */
export interface FindRequest {
  /**
   * Natural-language discovery query.
   * @minLength 1
   * @maxLength 1000
   * @pattern \S
   */
  query: string;
  /**
   * Maximum results from 1 to 100. Omit to return every remaining member,
   * capped at 100.
   * @minimum 1
   * @maximum 100
   * @multipleOf 1
   */
  limit?: number;
  /**
   * How much of each match to return. `summary` returns the light card;
   * `full` adds `agent_did` and the complete Profile. Defaults to `summary`.
   */
  detail?: "summary" | "full";
}

/** Ordered local Directory search result. */
export interface FindResult {
  /** Matches ordered by relevance, best first. */
  matches: DirectoryMatch[];
}

/** Directory lookup used by non-HTTP bindings. */
export interface GetProfileRequest {
  /** Local or same-Team qualified member Address. */
  address: Address;
}

/** MCP `ask` arguments. The server generates the request Message id. */
export interface AskToolRequest {
  /** Local or same-Team qualified recipient. */
  recipient: Address;
  /** Work input. */
  content: JsonValue;
  /**
   * Relative deadline from 1 to 86400 seconds.
   * @minimum 1
   * @maximum 86400
   * @multipleOf 1
   */
  deadline_seconds: number;
  /**
   * Local wait from 0 to 30 seconds. Defaults to 0.
   * @minimum 0
   * @maximum 30
   * @multipleOf 1
   */
  wait_seconds?: number;
  /**
   * Conversation to continue. Omit to start a fresh Thread; the server mints
   * one and the returned Ticket carries it.
   */
  thread_id?: Uuid;
  /**
   * Stable key so a retried tool call does not create a second request. When
   * present, the Message id is UUID5 of caller plus this key. When omitted,
   * the server includes the MCP JSON-RPC request id so a second distinct call
   * with the same arguments is a new Ticket, while a retry of the same request
   * is not.
   * @minLength 1
   * @maxLength 200
   */
  idempotency_key?: string;
}

/** MCP `tell` arguments. The server generates the event Message id. */
export interface TellToolRequest {
  /** Local or same-Team qualified recipient. */
  recipient: Address;
  /** Event data. */
  content: JsonValue;
  /** Conversation to continue. Omit to leave the event unthreaded. */
  thread_id?: Uuid;
  /**
   * Stable key so a retried tool call does not create a second event. Same
   * derivation rule as `AskToolRequest.idempotency_key`.
   * @minLength 1
   * @maxLength 200
   */
  idempotency_key?: string;
}

/** MCP roster resource body at `agentconnect://team/roster`. */
export interface TeamRoster {
  /** Team this roster belongs to. */
  team_name: TeamName;
  /** Every current Agent Membership. Principals, including `operator`, are omitted. */
  members: DirectoryEntry[];
}

/**
 * Closed set of Trace timeline event types.
 *
 * - `accepted`: the Runtime stored a Message.
 * - `ticket_opened`: a reply-expected request created a Ticket.
 * - `leased`: a Session took a Delivery.
 * - `completed`: `complete` finished the Delivery.
 * - `replied`: `reply` stored a response or error Message.
 * - `ticket_closed`: an open Ticket expired with no `reply` or `complete`.
 */
export type TraceEventType =
  | "accepted"
  | "ticket_opened"
  | "leased"
  | "completed"
  | "replied"
  | "ticket_closed";

/**
 * One recorded step of a causal operation. `get_trace` returns these in the
 * order the Runtime stored them.
 */
export interface TraceEvent {
  /** When the Runtime recorded the event. */
  at: Timestamp;
  /** What happened. */
  type: TraceEventType;
  /** Causal id shared with the Messages in this operation. */
  trace_id: Uuid;
  /** Membership that performed the step, or the requester for accept and open. */
  actor: QualifiedAddress;
  /** Message this step is about, when there is one. */
  message_id?: Uuid;
  /** Ticket this step is about, when there is one. */
  ticket_id?: Uuid;
  /**
   * Type-specific fields. `accepted` includes `kind`, `sender`, and
   * `recipient`. `leased` includes `attempt`. `replied` includes `outcome`
   * and `reply_id`. `ticket_closed` includes `state`. Unknown keys are
   * ignored by a Client.
   */
  detail: JsonObject;
}

/** Result of `get_trace`. */
export interface TraceResult {
  /** Requested causal id. */
  trace_id: Uuid;
  /** Recorded events, oldest first. */
  events: TraceEvent[];
}

/** One Membership row in `status`. */
export interface StatusMember {
  /** Canonical Agent name. */
  name: AgentName;
  /** Canonical qualified Address. */
  address: QualifiedAddress;
  /** True when the Membership has at least one unexpired Session. */
  online: boolean;
  /**
   * Queued plus leased Mailbox items. A principal has no Mailbox; this is 0.
   * @minimum 0
   * @multipleOf 1
   */
  mailbox_depth: number;
  /**
   * Open Tickets whose recipient is this Membership.
   * @minimum 0
   * @multipleOf 1
   */
  open_tickets: number;
}

/** Result of `status`. */
export interface StatusResult {
  /** Canonical Team name. */
  team_name: TeamName;
  /** Runtime restart guarantee. */
  persistence: PersistenceMode;
  /**
   * HTTP origin when the Runtime is serving, for example
   * `http://127.0.0.1:9000`. Omitted when it is not serving.
   */
  origin?: string;
  /**
   * Open Tickets in the Team.
   * @minimum 0
   * @multipleOf 1
   */
  open_tickets: number;
  /** Every Membership, including principals such as `operator`. Ordered by Address. */
  members: StatusMember[];
}

/** Operator input that creates a join token. */
export interface IssueJoinTokenRequest {
  /** Bind the token to this Agent name. */
  name?: AgentName;
  /** Bind the token to this Agent DID. */
  agent_did?: AgentDid;
  /**
   * Lifetime in seconds. Omit to use the Runtime default.
   * @minimum 1
   */
  ttl_seconds?: number;
  /** When true, a successful join consumes the token. Defaults to false. */
  single_use?: boolean;
}

/** Operator view of a join token the Runtime just issued. */
export interface JoinTokenIssued {
  /**
   * Secret the Agent sends as `join_token`. Keep it out of logs and Messages.
   * @minLength 1
   */
  token: string;
  /** Time after which this token cannot authenticate a join. */
  expires_at: Timestamp;
  /** Whether a successful join consumes the token. */
  single_use: boolean;
  /** Bound Agent name, when the operator set one. */
  name?: AgentName;
  /** Bound Agent DID, when the operator set one. */
  agent_did?: AgentDid;
}

/** Operator input that revokes a join token. */
export interface RevokeJoinTokenRequest {
  /**
   * Token secret to revoke.
   * @minLength 1
   */
  token: string;
}

/**
 * One event pushed on the Session event stream. `type` is open so new event
 * types are added over time; a Client MUST ignore an unknown type. This draft
 * defines `work_available`, whose `data` is `{}`, and `trace`, whose `data`
 * is a `TraceEvent`.
 */
export interface RuntimeEvent {
  /**
   * Event type name.
   * @pattern ^[a-z][a-z0-9_]{0,63}$
   */
  type: string;
  /** Type-specific data. */
  data: JsonObject;
}

/** Structured result used when an MCP tool reaches a Runtime failure. */
export interface ToolErrorResult {
  /** Runtime failure preserved without reinterpretation. */
  error: ErrorObject;
}

/**
 * Root used only to generate one JSON Schema containing every public object.
 * Applications exchange the referenced objects, not this wrapper.
 */
export interface AgentConnectPublicSchema {
  spec_version?: SpecVersion;
  address?: Address;
  qualified_address?: QualifiedAddress;
  collect_mode?: CollectMode;
  ticket_state?: TicketState;
  error_code?: ErrorCode;
  skill_example?: SkillExample;
  skill?: Skill;
  agent_profile?: AgentProfile;
  tag?: Tag;
  error?: ErrorObject;
  deadline_exceeded_error?: DeadlineExceededError;
  request_message?: RequestMessage;
  event_message?: EventMessage;
  mailbox_message?: MailboxMessage;
  response_message?: ResponseMessage;
  error_message?: ErrorMessage;
  message?: Message;
  delivery?: Delivery;
  ticket?: Ticket;
  directory_entry?: DirectoryEntry;
  directory_match?: DirectoryMatch;
  join_challenge?: JoinChallenge;
  join_request?: JoinRequest;
  runtime_limits?: RuntimeLimits;
  join_result?: JoinResult;
  heartbeat_result?: HeartbeatResult;
  callback_target?: CallbackTarget;
  send_request?: SendRequest;
  send_result?: SendResult;
  lease_request?: LeaseRequest;
  lease_result?: LeaseResult;
  complete_request?: CompleteRequest;
  complete_result?: CompleteResult;
  reply_request?: ReplyRequest;
  reply_result?: ReplyResult;
  get_result_request?: GetResultRequest;
  get_history_request?: GetHistoryRequest;
  history_result?: HistoryResult;
  find_request?: FindRequest;
  find_result?: FindResult;
  get_profile_request?: GetProfileRequest;
  ask_tool_request?: AskToolRequest;
  tell_tool_request?: TellToolRequest;
  team_roster?: TeamRoster;
  trace_event?: TraceEvent;
  trace_result?: TraceResult;
  status_member?: StatusMember;
  status_result?: StatusResult;
  issue_join_token_request?: IssueJoinTokenRequest;
  join_token_issued?: JoinTokenIssued;
  revoke_join_token_request?: RevokeJoinTokenRequest;
  runtime_event?: RuntimeEvent;
  tool_error_result?: ToolErrorResult;
}
