import { describe, expect, it, vi } from "vitest";

import { getListingVersion } from "./version";

describe("getListingVersion", () => {
  it("returns an opaque stable revision without exposing row counts or timestamps", async () => {
    const queryRaw = vi.fn().mockResolvedValue([
      {
        rowCount: "42",
        latestFirstFetchedAt: new Date("2026-07-14T04:30:00.000Z"),
      },
    ]);

    const first = await getListingVersion({ $queryRaw: queryRaw });
    const second = await getListingVersion({ $queryRaw: queryRaw });

    expect(first).toEqual(second);
    expect(Object.keys(first)).toEqual(["revision"]);
    expect(first.revision).toMatch(/^[\w-]{43}$/);
    expect(JSON.stringify(first)).not.toContain("42");
    expect(JSON.stringify(first)).not.toContain("2026-07-14");
  });

  it("changes revision when a new database row appears", async () => {
    const queryRaw = vi
      .fn()
      .mockResolvedValueOnce([
        {
          rowCount: "42",
          latestFirstFetchedAt: new Date("2026-07-14T04:30:00.000Z"),
        },
      ])
      .mockResolvedValueOnce([
        {
          rowCount: "43",
          latestFirstFetchedAt: new Date("2026-07-14T04:31:00.000Z"),
        },
      ]);

    const before = await getListingVersion({ $queryRaw: queryRaw });
    const after = await getListingVersion({ $queryRaw: queryRaw });

    expect(after.revision).not.toBe(before.revision);
  });

  it("returns a stable opaque revision before the first listing exists", async () => {
    const queryRaw = vi.fn().mockResolvedValue([]);

    const first = await getListingVersion({ $queryRaw: queryRaw });
    const second = await getListingVersion({ $queryRaw: queryRaw });

    expect(first).toEqual(second);
    expect(first.revision).toMatch(/^[\w-]{43}$/);
  });
});
