import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../services/api";

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("turns the server's error envelope into a readable ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: { code: "validation_failed", message: "Bad mapping.", details: [{ field: "expected_column", message: "required" }] } }), { status: 422 })));
    const err = await api.projects().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.message).toBe("Bad mapping. expected_column: required");
  });

  it("explains when the server cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("network"); }));
    await expect(api.projects()).rejects.toThrow("Cannot reach the Blindspot AI server");
  });
});
