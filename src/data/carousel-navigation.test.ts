import { describe, expect, it } from "vitest";

import { stepCarouselIndex } from "~/data/carousel-navigation";

describe("detail carousel navigation", () => {
  it("moves one image at a time", () => {
    expect(stepCarouselIndex(0, 1, 3)).toBe(1);
    expect(stepCarouselIndex(2, -1, 3)).toBe(1);
  });

  it("stops at both ends instead of looping", () => {
    expect(stepCarouselIndex(0, -1, 3)).toBe(0);
    expect(stepCarouselIndex(2, 1, 3)).toBe(2);
  });

  it("stays on the only image", () => {
    expect(stepCarouselIndex(0, 1, 1)).toBe(0);
  });
});
