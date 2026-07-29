import { describe, expect, it } from "vitest";

import {
  collectionCategories,
  formatListedAt,
  formatRupiah,
  listingPlatforms,
  platformMeta,
} from "~/data/listings";

describe("real listing presentation", () => {
  it("maps UI collections to the normalized database category vocabulary", () => {
    expect(collectionCategories("laptop")).toEqual(["Laptop"]);
    expect(collectionCategories("pc-build")).toEqual([
      "Desktop PC",
      "PC Case",
      "CPU",
      "RAM",
      "Storage",
      "Motherboard",
      "Power Supply",
    ]);
    expect(collectionCategories("gaming")).toEqual([
      "Game Console",
      "Game",
      "Controller",
      "Handheld PC",
    ]);
  });

  it("renders null prices honestly instead of treating them as free", () => {
    expect(formatRupiah(null)).toBe("Harga tidak dicantumkan");
  });

  it("formats the normalized listing date for Indonesian users", () => {
    const now = new Date("2026-07-14T12:00:00Z");
    expect(formatListedAt(new Date("2026-07-14T11:52:00Z"), now)).toBe(
      "8 menit lalu",
    );
  });

  it("keeps Facebook Marketplace and Facebook Groups distinct", () => {
    expect(listingPlatforms).toContain("facebook");
    expect(listingPlatforms).toContain("facebook_group");
    expect(platformMeta.facebook.label).toBe("Facebook Marketplace");
    expect(platformMeta.facebook_group.label).toBe("Facebook Grup JB");
  });
});
