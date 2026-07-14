export const listingSortOptions = [
  { value: "newest", label: "Terbaru" },
  { value: "price-high", label: "Harga tertinggi" },
  { value: "price-low", label: "Harga terendah" },
  { value: "available-first", label: "Ready stock" },
  { value: "sold-first", label: "Sold out" },
] as const;

export const listingSortValues = listingSortOptions.map(
  (option) => option.value,
) as [ListingSort, ...ListingSort[]];

export type ListingSort = (typeof listingSortOptions)[number]["value"];

export const defaultListingSort: ListingSort = "newest";

export function parseListingSort(value: string | null): ListingSort {
  return listingSortOptions.some((option) => option.value === value)
    ? (value as ListingSort)
    : defaultListingSort;
}

export function setListingSortParam(
  params: URLSearchParams,
  sort: ListingSort,
) {
  const next = new URLSearchParams(params.toString());

  if (sort === defaultListingSort) next.delete("sort");
  else next.set("sort", sort);

  return next;
}
