/**
 * Deterministic JSON Schema generator for AgentConnect.
 *
 * schema.ts is authoritative. schema.json is derived. Do not edit it by hand.
 */

import { createGenerator, type Config } from "ts-json-schema-generator";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const dir = dirname(fileURLToPath(import.meta.url));
const schemaTs = join(dir, "schema.ts");
const schemaJson = join(dir, "schema.json");
const tsconfig = join(dir, "tsconfig.json");

const config: Config = {
  path: schemaTs,
  tsconfig,
  type: "AgentConnectPublicSchema",
  additionalProperties: false,
  sortProps: true,
  minify: false,
  extraTags: ["stability", "format"],
  encodeRefs: true,
  skipTypeCheck: false,
};

function generate(): string {
  const schema = createGenerator(config).createSchema(config.type);
  const wrapped = {
    ...schema,
    $schema: "http://json-schema.org/draft-07/schema#",
    $id: "https://agentconnect.dev/spec/draft/schema.json",
    title: "AgentConnect Public Schema (pre-1.0 draft)",
    description:
      "Generated from schema.ts. Do not edit by hand. Run npm run generate.",
  };
  const ordered = {
    $schema: wrapped.$schema,
    $id: wrapped.$id,
    title: wrapped.title,
    description: wrapped.description,
    $ref: wrapped.$ref,
    definitions: wrapped.definitions,
  };
  return `${JSON.stringify(ordered, null, 2)}\n`;
}

const output = generate();
const check = process.argv.includes("--check");

if (check) {
  let existing = "";
  try {
    existing = readFileSync(schemaJson, "utf8");
  } catch {
    console.error("schema.json is missing. Run npm run generate.");
    process.exit(1);
  }
  const normalize = (s: string) => s.replace(/\r\n/g, "\n");
  if (normalize(existing) !== normalize(output)) {
    console.error(
      "schema.json is stale or was edited by hand. Run npm run generate.",
    );
    process.exit(1);
  }
  console.log("schema.json matches schema.ts");
  process.exit(0);
}

writeFileSync(schemaJson, output, "utf8");
console.log("wrote schema.json");
