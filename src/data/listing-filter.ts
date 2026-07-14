import {
  dummyListings,
  platformMeta,
  type ListingPlatform,
} from "~/data/dummy-listings";

export type ListingFilters = {
  platforms: ListingPlatform[];
  locations: string[];
  conditions: string[];
  minPrice: number | null;
  maxPrice: number | null;
};

type FilterableListing = {
  platform: ListingPlatform;
  location: string;
  condition: string;
  price: number | null;
};

const listingPlatforms = Object.keys(platformMeta) as ListingPlatform[];

export const listingLocations = Array.from(
  new Set(dummyListings.map((listing) => listing.location)),
).sort((left, right) => left.localeCompare(right, "id"));

export const listingConditions = Array.from(
  new Set(dummyListings.map((listing) => listing.condition)),
);

export const emptyListingFilters: ListingFilters = {
  platforms: [],
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

export function parseListingFilters(params: URLSearchParams): ListingFilters {
  return {
    platforms: parseRepeatedValues(params.getAll("platform"), listingPlatforms),
    locations: parseRepeatedValues(params.getAll("location"), listingLocations),
    conditions: parseRepeatedValues(
      params.getAll("condition"),
      listingConditions,
    ),
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
    "location",
    "condition",
    "minPrice",
    "maxPrice",
  ]) {
    next.delete(key);
  }

  for (const platform of filters.platforms) next.append("platform", platform);
  for (const location of filters.locations) next.append("location", location);
  for (const condition of filters.conditions)
    next.append("condition", condition);
  if (filters.minPrice !== null) next.set("minPrice", String(filters.minPrice));
  if (filters.maxPrice !== null) next.set("maxPrice", String(filters.maxPrice));

  return next;
}

export function filterListings<T extends FilterableListing>(
  listings: readonly T[],
  filters: ListingFilters,
) {
  const hasPriceFilter = filters.minPrice !== null || filters.maxPrice !== null;

  return listings.filter((listing) => {
    const platformMatches =
      filters.platforms.length === 0 ||
      filters.platforms.includes(listing.platform);
    const locationMatches =
      filters.locations.length === 0 ||
      filters.locations.includes(listing.location);
    const conditionMatches =
      filters.conditions.length === 0 ||
      filters.conditions.includes(listing.condition);
    const priceMatches =
      !hasPriceFilter ||
      (listing.price !== null &&
        (filters.minPrice === null || listing.price >= filters.minPrice) &&
        (filters.maxPrice === null || listing.price <= filters.maxPrice));

    return (
      platformMatches && locationMatches && conditionMatches && priceMatches
    );
  });
}

export function countActiveFilterGroups(filters: ListingFilters) {
  return [
    filters.platforms.length > 0,
    filters.locations.length > 0,
    filters.conditions.length > 0,
    filters.minPrice !== null || filters.maxPrice !== null,
  ].filter(Boolean).length;
}
