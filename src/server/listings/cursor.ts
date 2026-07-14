import { z } from "zod";

const encodedCursorSchema = z.object({
  v: z.literal(3),
  s: z.enum([
    "newest",
    "price-high",
    "price-low",
    "available-first",
    "sold-first",
  ]),
  r: z.number().int().min(0).max(2),
  k: z.number().int(),
  t: z.string().datetime({ offset: true }),
  i: z.string().min(1).max(128),
});

export interface ListingCursor {
  sort:
    "newest" | "price-high" | "price-low" | "available-first" | "sold-first";
  statusRank: number;
  sortValue: number;
  effectiveAt: Date;
  id: string;
}

export class InvalidListingCursorError extends Error {
  constructor() {
    super("Invalid listing feed cursor");
    this.name = "InvalidListingCursorError";
  }
}

export function encodeListingCursor(cursor: ListingCursor): string {
  const encoded = encodedCursorSchema.parse({
    v: 3,
    s: cursor.sort,
    r: cursor.statusRank,
    k: cursor.sortValue,
    t: cursor.effectiveAt.toISOString(),
    i: cursor.id,
  });

  return Buffer.from(JSON.stringify(encoded), "utf8").toString("base64url");
}

export function decodeListingCursor(value: string): ListingCursor {
  try {
    if (!/^[A-Za-z0-9_-]+$/.test(value) || value.length > 512) {
      throw new Error("invalid base64url");
    }

    const json = Buffer.from(value, "base64url").toString("utf8");
    const parsed = encodedCursorSchema.parse(JSON.parse(json));

    return {
      sort: parsed.s,
      statusRank: parsed.r,
      sortValue: parsed.k,
      effectiveAt: new Date(parsed.t),
      id: parsed.i,
    };
  } catch {
    throw new InvalidListingCursorError();
  }
}
