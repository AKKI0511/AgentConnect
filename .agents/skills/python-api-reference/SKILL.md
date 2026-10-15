---
name: python-api-reference
description: Write and review public Python SDK references, docstrings and examples. Use for clear package overviews, API contracts and generated reference pages for developers and coding agents, not tool catalogs or runtime prompts.
---

# Python API reference writing

Help a caller choose an API, use it correctly and understand the result. Write an API reference, not an application walkthrough. Assume Python and relevant domain knowledge, such as agents, harnesses, memory or MCP, but no product vocabulary.

Read [writing examples](references/writing-examples.md) when editing overviews or examples. Its paired examples explain the intended scope and tone.

## Keep only what helps the caller

Keep a detail if it changes what the caller chooses, writes, expects or handles. Otherwise leave it out.

- Explain inputs, results, required setup and relevant errors.
- Explain resource ownership, timeouts or persistence only where they affect use.
- For subclass authors, explain what to implement and how its result is used.
- Leave out internal call chains, import tricks, storage algorithms, development history and maintainer instructions.
- Separate everyday APIs, supported extension contracts and internal plumbing when reviewing the delivered surface. Trace callers before proposing removal; a reference edit does not authorize API redesign.
- Describe the visible effect. For example, say “Closing the client leaves accepted jobs running.” The caller does not need the internal shutdown sequence.

Authoring rules and research belong in this skill. Published reference pages contain only user guidance.

## Give each level a job

| Level | Reader's question |
| --- | --- |
| Root package / landing page | What is this SDK for, and which local concepts do I need? |
| Subpackage `__init__.py` | What is this area for, what does it need, and how do I use it? |
| Leaf module | What does this particular file provide? |
| Class / constructor | What does this object represent, and how do I obtain or subclass it? |
| Method / function | What is the contract, and when does this call help? |
| Field / property | What does this value mean? |

Check which source becomes each page. Some initializers only export names; another page supplies the overview. Follow the actual site structure.

Start the root with one plain sentence stating the benefit or purpose. Introduce only the local nouns needed to understand the entry point. An optional short fragment can show why the SDK exists around an existing framework or resource. Avoid feature catalogs and symbol lists already supplied by navigation or generated reference pages.

Make each subpackage introduction self-contained and conversational. Explain its purpose, prerequisites and use without enumerating methods. Give leaf modules a sentence specific to their contents. For classes, explain the object's role, how callers obtain it and any relevant subclass or lifecycle contract. Objects supplied by a factory or handler rarely need constructor internals.

Keep shared explanations in one place and link to useful concepts or guides. Name assumed objects locally; do not make a fragment depend on an example on another reference page. Repeat a short prerequisite or state check when a method needs it to make sense on its own.

## Write for quick reading

- Lead with the useful action or result. Use everyday words and exact API names.
- Prefer one idea per paragraph, usually one to three short sentences.
- Use a short list for alternatives or steps. Use a table only when comparison is easier that way.
- Treat the signature as already read. Do not restate types, default values, obvious parameter names or the return annotation. Omit Args/Returns entries that add nothing; no section is mandatory merely because a parameter exists. Explain only domain meaning, constraints, authority, ownership, side effects or special-value behavior the signature cannot express.
- Use plain, conversational, direct prose. Remove marketing, feature pitches, meta prose, implementation narration, contrived contrasts and Python tutorials.
- Keep scope words exact: another process is not necessarily another host, and stopping a listener is not restarting its clients. Preserve reachability, authority and resource-ownership conditions when shortening prose.
- Explain the consequence of omission only when it is non-obvious (for example, inheriting a deadline or selecting memory storage). Do not repeat the literal default. Keep units or bounds only when names/types do not fully convey them.
- Link extended workflows to guides. Keep advanced details here when they change caller choices or results.

Keep essential facts even when they take more space. Shorter text must still explain how to use the API correctly.

## Choose examples by need

Use an example to clarify a choice, a difficult input or a result. Simple accessors often need none.

| Example | Include |
| --- | --- |
| Complete program, when needed | Imports, stated setup, real calls, a useful result and cleanup. |
| Focused fragment | A short caption naming the existing client, resource or async context. |
| Input/output shape | The relevant value, labelled as input or output. |

- Prefer focused fragments with named assumptions. Complete runners, provider authentication, startup, polling loops and background scheduling usually belong in guides. Include them here when the specific API being taught requires them; async code and loops are not inherently too much.
- Include imports for newly introduced types. Use real public calls, not invented helpers.
- For framework adapters, assume an existing configured harness when that keeps the integration clear. Verify the framework's real public API and result access. Explain integration boundaries accurately; connecting a resource does not necessarily install its tools or capabilities in a model.
- Do not fabricate model response schemas or implement a toy harness to make a reference example executable. Keep test doubles and setup in tests. Disclose limits on verification in the author report.
- Check result states before reading fields that may be absent. Distinguish returned failures from exceptions.
- Show output when it adds meaning. Label variable output as illustrative.
- Use familiar sample data and the smallest example that teaches a practical choice, input or result. An obvious call or a canned miss teaches little. Not every symbol needs an example.

## Verify before publishing

These steps are for the author; keep them out of user-facing prose.

1. Read signatures and behavior. Check inherited docs and overloads before calling something undocumented. Preserve runtime behavior, exports and tested tool/schema text. A docstring naming a specific result does not repair an Any/dict annotation. Compare interface annotations with real implementations and flag mismatches separately from prose. Model docstrings may become schema descriptions delivered to tools; inspect that output too.
2. Edit the source. Follow the configured docstring format and link syntax. Avoid duplicating constructor parameters when the renderer merges them into the class.
3. Regenerate the affected pages. Inspect the whole delivered page, including unchanged members: blank attribute sections, repeated parameter prose and internal helpers can overwhelm a concise introduction. Report pre-existing surface problems separately from new writing defects. Inspect signatures, links, code blocks and result descriptions. Keep site markup out of Python snippets.
4. Follow the user's verification scope. For prose-only changes, inspect source and regenerated output; do not add or run tests by habit. When executable examples or implementation change and testing is authorized, exercise representative behavior with setup off-page. Distinguish reported checks from checks you ran, and never call a fragment verified solely because it compiles.
5. Read the main user journey and one method in isolation. Remove anything neither reader needs. Review all public symbols in scope; retain good existing text.

Keep repository commands and publishing policy in project-local instructions. Preserve tool catalogs and prompts during a reference-only edit.

## Research when choosing a pattern

The [source comparison](references/sdk-reference-research.md) records examples from Prime Intellect, Anthropic, OpenAI, LangChain and Cursor. Read the relevant section when choosing a structure; ordinary edits need not reload the whole report.

To refresh it, compare root, subpackage and leaf-module docs with the published reference. Record the revision, exact sources, example setup and any gaps. Separate observed practice from your recommendation. Borrow only what helps the reader.
