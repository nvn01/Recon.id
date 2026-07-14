import { z } from "zod";

const encodedCursorSchema = z.object({
  v: z.literal(2),
  r: z.number().int().min(0).max(1),
  t: z.string().datetime({ offset: true }),
  i: z.string().min(1).max(128),
});

export interface ListingCursor {
  statusRank: number;
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
    v: 2,
    r: cursor.statusRank,
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
      statusRank: parsed.r,
      effectiveAt: new Date(parsed.t),
      id: parsed.i,
    };
  } catch {
    throw new InvalidListingCursorError();
  }
}
