import { describe, expect, it } from "vitest";

import { buildHomeMetadata } from "~/lib/home-metadata";

describe("root feed metadata", () => {
  it("makes the unfiltered root feed canonical and indexable", async () => {
    const metadata = buildHomeMetadata({});

    expect(metadata.alternates).toEqual({ canonical: "/" });
    expect(metadata.robots).toEqual({ index: true, follow: true });
    expect(metadata.openGraph).toEqual(expect.objectContaining({ url: "/" }));
  });

  it("keeps filtered root URLs crawlable but out of the index", async () => {
    const metadata = buildHomeMetadata({
      platform: ["reddit", "facebook"],
    });

    expect(metadata.alternates).toEqual({ canonical: "/" });
    expect(metadata.robots).toEqual({ index: false, follow: true });
  });
});
