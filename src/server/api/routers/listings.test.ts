import { TRPCError } from "@trpc/server";
import { describe, expect, it, vi } from "vitest";

import { listingsRouter } from "./listings";

const createCaller = (queryRaw: ReturnType<typeof vi.fn>) =>
  listingsRouter.createCaller({
    db: {
      $queryRaw: queryRaw,
      listing: { findMany: vi.fn() },
    } as never,
    headers: new Headers(),
  });

describe("listingsRouter.feed", () => {
  it("exposes the public feed with default input", async () => {
    const caller = createCaller(vi.fn().mockResolvedValue([]));

    await expect(caller.feed()).resolves.toEqual({
      items: [],
      nextCursor: null,
      hasNextPage: false,
    });
  });

  it("translates malformed cursors to a safe BAD_REQUEST", async () => {
    const caller = createCaller(vi.fn());

    await expect(caller.feed({ cursor: "not-base64!" })).rejects.toMatchObject({
      code: "BAD_REQUEST",
      message: "Invalid listing feed cursor",
    } satisfies Partial<TRPCError>);
  });

  it("does not replace unexpected database errors with cursor errors", async () => {
    const caller = createCaller(
      vi.fn().mockRejectedValue(new Error("database unavailable")),
    );

    await expect(caller.feed()).rejects.toThrow("database unavailable");
  });
});
