import { describe, expect, it } from "vitest";

import {
  distributeAcrossColumns,
  getMasonryColumnCount,
} from "~/data/masonry-layout";

describe("responsive masonry layout", () => {
  it("uses two to five columns at the feed breakpoints", () => {
    expect(getMasonryColumnCount(390)).toBe(2);
    expect(getMasonryColumnCount(760)).toBe(2);
    expect(getMasonryColumnCount(900)).toBe(3);
    expect(getMasonryColumnCount(1200)).toBe(4);
    expect(getMasonryColumnCount(1440)).toBe(5);
  });

  it("places sparse category listings across the first row", () => {
    expect(distributeAcrossColumns(["one", "two", "three", "four"], 5)).toEqual(
      [["one"], ["two"], ["three"], ["four"], []],
    );
  });

  it("continues down each column after filling the first row", () => {
    expect(distributeAcrossColumns([1, 2, 3, 4, 5, 6, 7], 3)).toEqual([
      [1, 4, 7],
      [2, 5],
      [3, 6],
    ]);
  });
});
