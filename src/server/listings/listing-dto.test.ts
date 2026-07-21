import { describe, expect, it } from "vitest";

import { toListingDto, type ListingFeedRecord } from "./listing-dto";

const listing: ListingFeedRecord = {
  id: "listing-1",
  platform: "INSTAGRAM",
  sourceUrl: "https://www.instagram.com/p/example/",
  title: "RTX 4070",
  description: "Full seller caption",
  category: "GPU",
  brand: "NVIDIA",
  price: 7_500_000,
  locationTexts: ["Jakarta"],
  conditionText: "Used",
  sellerName: "seller",
  moderation: null,
  status: "AVAILABLE",
  postedAt: null,
  firstFetchedAt: new Date("2026-07-12T10:00:00Z"),
  images: [
    {
      sourceUrl: "https://scontent.example/image-2.jpg",
      cachedUrl: "https://media.app-pixel.com/production/instagram/aa/two.jpg",
      position: 2,
      altText: null,
    },
    {
      sourceUrl: "javascript:alert(1)",
      cachedUrl: null,
      position: 1,
      altText: "unsafe",
    },
    {
      sourceUrl: "not-a-url",
      cachedUrl: null,
      position: 3,
      altText: "malformed",
    },
    {
      sourceUrl: "https://scontent.example/image-0.jpg",
      cachedUrl: null,
      position: 0,
      altText: "front",
    },
  ],
};

describe("toListingDto", () => {
  it("maps the database record to the public DB-shaped contract", () => {
    expect(toListingDto(listing)).toEqual({
      id: "listing-1",
      platform: "instagram",
      sourceUrl: "https://www.instagram.com/p/example/",
      title: "RTX 4070",
      description: "Full seller caption",
      category: "GPU",
      brand: "NVIDIA",
      price: 7_500_000,
      currency: "IDR",
      locationTexts: ["Jakarta"],
      conditionText: "Used",
      sellerName: "seller",
      status: "available",
      listedAt: new Date("2026-07-12T10:00:00Z"),
      images: [
        {
          sourceUrl: "https://scontent.example/image-0.jpg",
          position: 0,
          altText: "front",
        },
        {
          sourceUrl: "https://media.app-pixel.com/production/instagram/aa/two.jpg",
          position: 2,
          altText: null,
        },
      ],
    });
  });

  it("fails closed when the original listing URL is not HTTPS", () => {
    expect(() =>
      toListingDto({ ...listing, sourceUrl: "http://example.com/listing" }),
    ).toThrow("listing source URL must use HTTPS");
  });

  it("uses original media for non-Instagram listings even if cached metadata is present", () => {
    expect(
      toListingDto({ ...listing, platform: "FACEBOOK" }).images[1]?.sourceUrl,
    ).toBe("https://scontent.example/image-2.jpg");
  });

  it("uses the manually corrected seller name when one exists", () => {
    expect(
      toListingDto({
        ...listing,
        moderation: { sellerNameOverride: "Correct Facebook Seller" },
      }).sellerName,
    ).toBe("Correct Facebook Seller");
  });

  it("falls back to the original Instagram media URL when the cached URL is unsafe", () => {
    const images = listing.images.map((image) =>
      image.position === 2 ? { ...image, cachedUrl: "http://media.example/image.jpg" } : image,
    );
    expect(toListingDto({ ...listing, images }).images[1]?.sourceUrl).toBe(
      "https://scontent.example/image-2.jpg",
    );
  });

  it("rejects an HTTPS cached URL outside the dedicated Cloudflare media origin", () => {
    const images = listing.images.map((image) =>
      image.position === 2
        ? { ...image, cachedUrl: "https://attacker.example/production/instagram/image.jpg" }
        : image,
    );
    expect(toListingDto({ ...listing, images }).images[1]?.sourceUrl).toBe(
      "https://scontent.example/image-2.jpg",
    );
  });

  it("omits location values that look like contact data or oversized parser output", () => {
    expect(
      toListingDto({
        ...listing,
        locationTexts: [
          " Bandung ",
          "081234567890",
          "https://example.com/location",
          "x".repeat(81),
        ],
      }).locationTexts,
    ).toEqual(["Bandung"]);
  });

  it("presents historical zero or known placeholder prices as unknown", () => {
    expect(toListingDto({ ...listing, price: 0 }).price).toBeNull();
    expect(toListingDto({ ...listing, price: 123 }).price).toBeNull();
    expect(toListingDto({ ...listing, price: 123_456 }).price).toBeNull();
  });
});
