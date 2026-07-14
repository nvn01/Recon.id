import { type ListingStatus } from "~/data/dummy-listings";

export const listingSortOptions = [
  { value: "newest", label: "Terbaru" },
  { value: "price-high", label: "Harga tertinggi" },
  { value: "price-low", label: "Harga terendah" },
  { value: "available-first", label: "Ready stock" },
  { value: "sold-first", label: "Sold out" },
] as const;

export type ListingSort = (typeof listingSortOptions)[number]["value"];

export const defaultListingSort: ListingSort = "newest";

type SortableListing = {
  price: number | null;
  status: ListingStatus;
};

const defaultStatusRank: Record<ListingStatus, number> = {
  available: 0,
  unknown: 0,
  sold: 1,
};

const availableFirstRank: Record<ListingStatus, number> = {
  available: 0,
  unknown: 1,
  sold: 2,
};

const soldFirstRank: Record<ListingStatus, number> = {
  sold: 0,
  available: 1,
  unknown: 1,
};

export function parseListingSort(value: string | null): ListingSort {
  return listingSortOptions.some((option) => option.value === value)
    ? (value as ListingSort)
    : defaultListingSort;
}

export function sortListings<T extends SortableListing>(
  listings: readonly T[],
  sort: ListingSort,
): T[] {
  const ranked = listings.map((listing, index) => ({ listing, index }));

  ranked.sort((left, right) => {
    const rank =
      sort === "available-first"
        ? availableFirstRank
        : sort === "sold-first"
          ? soldFirstRank
          : defaultStatusRank;
    const statusDifference =
      rank[left.listing.status] - rank[right.listing.status];

    if (statusDifference !== 0) return statusDifference;

    if (sort === "price-high" || sort === "price-low") {
      const leftPrice = left.listing.price;
      const rightPrice = right.listing.price;

      if (leftPrice === null && rightPrice !== null) return 1;
      if (leftPrice !== null && rightPrice === null) return -1;

      if (leftPrice !== null && rightPrice !== null) {
        const priceDifference =
          sort === "price-high"
            ? rightPrice - leftPrice
            : leftPrice - rightPrice;
        if (priceDifference !== 0) return priceDifference;
      }
    }

    return left.index - right.index;
  });

  return ranked.map(({ listing }) => listing);
}
