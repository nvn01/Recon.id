import type { TRPCError } from "@trpc/server";
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

  it("does not expose unexpected database error details", async () => {
    const caller = createCaller(
      vi
        .fn()
        .mockRejectedValue(
          new Error("connect ECONNREFUSED postgresql://internal-host/recon"),
        ),
    );

    await expect(caller.feed()).rejects.toMatchObject({
      code: "INTERNAL_SERVER_ERROR",
      message: "Unable to load listing feed",
    } satisfies Partial<TRPCError>);
  });
});

describe("listingsRouter.version", () => {
  it("exposes only the opaque listing revision", async () => {
    const caller = createCaller(
      vi.fn().mockResolvedValue([
        {
          rowCount: "7",
          latestFirstFetchedAt: new Date("2026-07-14T04:30:00.000Z"),
        },
      ]),
    );

    const result = await caller.version();

    expect(Object.keys(result)).toEqual(["revision"]);
    expect(result.revision).toMatch(/^[\w-]{43}$/);
  });

  it("does not expose unexpected database error details", async () => {
    const caller = createCaller(
      vi
        .fn()
        .mockRejectedValue(
          new Error("connect ECONNREFUSED postgresql://internal-host/recon"),
        ),
    );

    await expect(caller.version()).rejects.toMatchObject({
      code: "INTERNAL_SERVER_ERROR",
      message: "Unable to check for new listings",
    } satisfies Partial<TRPCError>);
  });
});
