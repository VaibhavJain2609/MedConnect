#!/usr/bin/env node
/**
 * Generate TypeScript types from the backend's OpenAPI schema.
 *
 * Input:  frontend/openapi.json  (gitignored — produced by
 *         `cd backend && python scripts/export_openapi.py`)
 * Output: src/lib/api/schema.d.ts (committed — CI verifies it stays in sync)
 *
 * Usage:
 *   node scripts/gen-api-types.mjs           regenerate schema.d.ts
 *   node scripts/gen-api-types.mjs --check   fail if schema.d.ts is stale (CI)
 */

import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const input = join(frontendRoot, "openapi.json");
const output = join(frontendRoot, "src/lib/api/schema.d.ts");
const cli = join(frontendRoot, "node_modules/openapi-typescript/bin/cli.js");

const check = process.argv.includes("--check");

if (!existsSync(input)) {
  console.error(
    `Missing ${relative(process.cwd(), input)}.\n\n` +
      "Export it from the backend first (no DB/server needed):\n\n" +
      "  cd backend && python scripts/export_openapi.py\n",
  );
  process.exit(1);
}

// --alphabetize keeps the generated file diff-stable regardless of spec
// key ordering; --check diffs the existing file against a fresh generate.
const args = [cli, input, "--output", output, "--alphabetize"];
if (check) args.push("--check");

execFileSync(process.execPath, args, { stdio: "inherit" });
