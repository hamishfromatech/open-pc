import { defineConfig } from "@hey-api/openapi-ts";

// Generates a typed TypeScript client from the committed OpenAPI contract
// (dashboard/openapi.json), which is dumped from the FastAPI agent server by
// `python scripts/dump_openapi.py`. The server stays the single source of
// truth; CI fails if the committed spec drifts from the live server.
//
// Regenerate after the spec changes:
//   python scripts/dump_openapi.py && npm run generate
export default defineConfig({
  input: "./openapi.json",
  output: "./src/api/client",
  plugins: ["@hey-api/client-fetch"],
});