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
  status: "AVAILABLE",
  postedAt: null,
  firstFetchedAt: new Date("2026-07-12T10:00:00Z"),
  images: [
    {
      sourceUrl: "https://scontent.example/image-2.jpg",
      position: 2,
      altText: null,
    },
    {
      sourceUrl: "javascript:alert(1)",
      position: 1,
      altText: "unsafe",
    },
    {
      sourceUrl: "not-a-url",
      position: 3,
      altText: "malformed",
    },
    {
      sourceUrl: "https://scontent.example/image-0.jpg",
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
          sourceUrl: "https://scontent.example/image-2.jpg",
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

  it("presents historical zero or placeholder-small prices as unknown", () => {
    expect(toListingDto({ ...listing, price: 0 }).price).toBeNull();
    expect(toListingDto({ ...listing, price: 123 }).price).toBeNull();
  });
});
