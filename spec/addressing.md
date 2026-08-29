# Addressing and discovery

An Agent has one name inside a Team. The Runtime combines the Agent name and Team name into a canonical Address.

The current draft resolves Addresses only inside the current Team. A qualified location is still part of the grammar and is validated before scope is checked.

## Agent names

An Agent name in canonical form:

- contains 1 to 63 lowercase ASCII characters
- begins and ends with a letter or digit
- may contain letters, digits, `-`, and `_` between them

```text
agent-name   = alphanumeric [ 0*61( name-character ) alphanumeric ]
name-character = alphanumeric / "-" / "_"
alphanumeric = ALPHA / DIGIT
```

`ALPHA` means an ASCII letter. Input may contain uppercase ASCII letters. The Runtime canonicalizes submitted names to lowercase before uniqueness checks and MUST reject non-ASCII characters or names that do not match the grammar.

Examples:

| Input | Result |
| --- | --- |
| `researcher` | valid |
| `code_reviewer` | valid |
| `agent-2` | valid |
| `Researcher` | canonical `researcher` |
| `_writer` | invalid |
| `writer-` | invalid |
| `a..b` | invalid |

## Team names

A Team name is a lowercase DNS label:

- contains 1 to 63 lowercase ASCII characters
- begins and ends with a letter or digit
- may contain letters, digits, and `-` between them

Underscores are not allowed in Team names.

```text
dns-label = alphanumeric [ 0*61( alphanumeric / "-" ) alphanumeric ]
```

## Address grammar

```text
address  = agent-name [ "@" location ]
location = dns-label *( "." dns-label )
```

A location contains at most 253 characters. The grammar does not accept a trailing dot.

An unqualified Address such as `writer` is relative to the caller's Team. A qualified Address such as `writer@content-squad` names both parts. A multi-label location such as `writer@legal.acme.com` is valid grammar; the canonical Address type already represents it, so nothing about stored Addresses changes when cross-team resolution is added later.

An accepted Message always stores qualified canonical Addresses, even when `SendRequest.recipient` was unqualified.

The current draft resolves a qualified Address only when its location equals the Runtime's `team_name`. Any other valid location fails with `address_outside_team`. Invalid syntax fails with `invalid_address`.

### Parse and resolution vectors

Assume the current Team is `content-squad`.

| Input | Parsed name | Parsed location | Resolution |
| --- | --- | --- | --- |
| `writer` | `writer` | absent | `writer@content-squad` |
| `writer@content-squad` | `writer` | `content-squad` | `writer@content-squad` |
| `Writer@Content-Squad` | `writer` | `content-squad` | `writer@content-squad` |
| `writer@legal.example.com` | `writer` | `legal.example.com` | `address_outside_team` |
| `@content-squad` | none | none | `invalid_address` |
| `writer@` | none | none | `invalid_address` |
| `writer@team@host` | none | none | `invalid_address` |
| `writer/content-squad` | none | none | `invalid_address` |
| empty string | none | none | `invalid_address` |

## Name ownership

Agent names are unique within a Team.

- A name and Agent DID that are both unused may create a Membership.
- The same name and Agent DID reconnect to their existing Membership, whether as the same Instance or an additional one.
- A name bound to another DID fails `name_conflict`.
- A DID bound to another name fails `name_conflict`.

Changing an Agent's name is not defined in the current draft. The Runtime MUST NOT silently rename a Membership during `join`.

## Profile

A Profile is discovery information only. It describes what one participant can do, the way a short bio describes a person. Identity, name, Address, Session data, and routing data belong to the Membership and Directory entry, not the Profile.

An `AgentProfile` has:

- a required `summary`
- one or more `skills`
- an optional longer `description`
- optional lowercase `tags`

A Skill is a natural-language claim, not a typed endpoint. It has a unique `name` within the Profile, a required `description`, optional text `examples`, and optional `tags`. A Skill carries no input or output schema: an Agent is addressed as one conversational participant, a caller describes work in free-form `content`, and no request is dispatched against a declared Skill signature. Skills exist to make discovery specific and to show a reader what the Agent is for.

The Runtime rejects a Profile when:

- `summary` contains no non-whitespace character or is longer than 200 characters
- `description` is present but contains no non-whitespace character or is longer than 2,000 characters
- `skills` is empty, has more than 50 entries, or repeats a Skill name
- a Skill description contains no non-whitespace character or is longer than 1,000 characters
- a Skill has more than 10 examples, or an example is empty or longer than 500 characters
- a Skill has more than 20 tags, repeats a tag, or has a tag outside the tag grammar
- `tags` has more than 20 entries, repeats a value, or contains a value outside the tag grammar

### Profile example

```json
{
  "summary": "Researches technical topics and returns cited findings.",
  "description": "Use for source discovery, comparison, and concise evidence summaries.",
  "skills": [
    {
      "name": "technical_research",
      "description": "Find and compare primary technical sources, then summarize with citations.",
      "examples": [
        "Compare two message-queue designs and cite the tradeoffs.",
        "Find the primary source behind a benchmark claim."
      ],
      "tags": ["research"]
    }
  ],
  "tags": ["research", "technical"]
}
```

Profiles are descriptive claims made by the Agent owner. The Runtime validates shape but does not certify that an Agent performs a Skill well.

## Directory

The Directory contains one `DirectoryEntry` per Membership:

- canonical Address
- Agent DID
- Profile

The Directory includes offline Memberships because Membership and presence are separate. An offline Agent may still receive queued work.

## `find`

`find` performs local discovery from a natural-language query containing 1 to 1,000 characters and at least one non-whitespace character.

The result is an ordered list of matches, best first, with no scores. Scores are implementation-specific and would imply a precision the specification does not define.

Discovery is written for a model deciding who to hire, so it is cheap by default. Each match is a light card: the Address to send to, the Profile `summary`, the Agent's Skill names for a quick capability scan, and any tags. A model skims the ranked cards, then reads the one it wants in full with `get_profile`. When a caller wants everything inline, `detail=full` adds the Agent DID and the complete Profile to every match.

The Runtime searches every Membership except the caller. Matches are ordered by relevance, with equal-relevance entries ordered by canonical Address.

`limit` is optional. When omitted, `find` returns every remaining member, at most 100. When present it MUST be between `1` and `100` and caps the list. A Team of 15 and a Team of 150 use the same request.

Search MUST work on a fresh Team without optional infrastructure. The search method is an implementation choice, but changing it MUST NOT change the request or result shape. A future policy layer may hide some members from some callers; that filters the result list and does not change its shape, and a later cross-Team scope adds reach rather than a new result type.

### Default size vectors

The caller is excluded. Other members are the rest of the Team.

| Other members | `limit` | Result size |
| --- | --- | --- |
| 8 | omitted | 8 |
| 15 | omitted | 15 |
| 150 | omitted | 100 |
| 15 | 3 | 3 |

### Search example

Request:

```json
{
  "query": "someone who can verify a contract",
  "limit": 2
}
```

Result:

```json
{
  "matches": [
    {
      "address": "contract-reviewer@content-squad",
      "summary": "Reviews contracts for risk and missing terms.",
      "skill_names": ["contract_review"],
      "tags": ["contracts", "legal"]
    }
  ]
}
```

The same query with `detail=full` returns each match with `agent_did` and the complete `profile` added.

## `get_profile`

`get_profile` returns one full `DirectoryEntry` by local or same-Team qualified Address. Missing members return `not_found`.

Profile access is explicit. The Runtime MUST NOT prepend a Profile to a Message, Delivery, Thread history, or handler input. A Client may pass Profile data to its Agent after explicitly calling `find` or `get_profile`.
