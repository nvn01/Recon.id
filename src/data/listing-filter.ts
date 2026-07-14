import {
  listingPlatforms,
  listingStatuses,
  type ListingPlatform,
  type ListingStatus,
} from "~/data/listings";

export type ListingFilters = {
  platforms: ListingPlatform[];
  statuses: ListingStatus[];
  locations: string[];
  conditions: string[];
  minPrice: number | null;
  maxPrice: number | null;
};

export const emptyListingFilters: ListingFilters = {
  platforms: [],
  statuses: [],
  locations: [],
  conditions: [],
  minPrice: null,
  maxPrice: null,
};

function parsePrice(value: string | null) {
  if (!value) return null;

  const price = Number(value);
  return Number.isSafeInteger(price) && price >= 0 ? price : null;
}

function parseRepeatedValues<T extends string>(
  values: string[],
  validValues: readonly T[],
) {
  return Array.from(
    new Set(
      values.filter((value): value is T => validValues.includes(value as T)),
    ),
  );
}

function parseTextValues(values: string[]) {
  return Array.from(
    new Set(
      values
        .map((value) => value.trim())
        .filter((value) => value.length > 0 && value.length <= 80),
    ),
  ).slice(0, 10);
}

export function parseListingFilters(params: URLSearchParams): ListingFilters {
  return {
    platforms: parseRepeatedValues(params.getAll("platform"), listingPlatforms),
    statuses: parseRepeatedValues(params.getAll("status"), listingStatuses),
    locations: parseTextValues(params.getAll("location")),
    conditions: parseTextValues(params.getAll("condition")),
    minPrice: parsePrice(params.get("minPrice")),
    maxPrice: parsePrice(params.get("maxPrice")),
  };
}

export function setListingFilterParams(
  params: URLSearchParams,
  filters: ListingFilters,
) {
  const next = new URLSearchParams(params.toString());

  for (const key of [
    "platform",
    "status",
    "location",
    "condition",
    "minPrice",
    "maxPrice",
  ]) {
    next.delete(key);
  }

  for (const platform of filters.platforms) next.append("platform", platform);
  for (const status of filters.statuses) next.append("status", status);
  for (const location of filters.locations) next.append("location", location);
  for (const condition of filters.conditions)
    next.append("condition", condition);
  if (filters.minPrice !== null) next.set("minPrice", String(filters.minPrice));
  if (filters.maxPrice !== null) next.set("maxPrice", String(filters.maxPrice));

  return next;
}

export function countActiveFilterGroups(filters: ListingFilters) {
  return [
    filters.platforms.length > 0,
    filters.statuses.length > 0,
    filters.locations.length > 0,
    filters.conditions.length > 0,
    filters.minPrice !== null || filters.maxPrice !== null,
  ].filter(Boolean).length;
}
