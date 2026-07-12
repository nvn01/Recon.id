import { describe, expect, it } from "vitest";

import {
  decodeListingCursor,
  encodeListingCursor,
  InvalidListingCursorError,
} from "./cursor";

describe("listing feed cursor", () => {
  it("round-trips the ranked keyset without exposing plain JSON", () => {
    const value = {
      statusRank: 1,
      effectiveAt: new Date("2026-07-12T10:19:21.617Z"),
      id: "listing-123",
    } as const;

    const cursor = encodeListingCursor(value);

    expect(cursor).not.toContain("listing-123");
    expect(decodeListingCursor(cursor)).toEqual(value);
  });

  it.each([
    "not base64!",
    Buffer.from("not-json").toString("base64url"),
    Buffer.from(
      JSON.stringify({ v: 2, r: 0, t: new Date().toISOString(), i: "id" }),
    ).toString("base64url"),
    Buffer.from(
      JSON.stringify({ v: 1, r: 4, t: new Date().toISOString(), i: "id" }),
    ).toString("base64url"),
    Buffer.from(
      JSON.stringify({ v: 1, r: 0, t: "not-a-date", i: "id" }),
    ).toString("base64url"),
  ])("rejects malformed or unsupported cursors", (cursor) => {
    expect(() => decodeListingCursor(cursor)).toThrow(
      InvalidListingCursorError,
    );
  });
});
