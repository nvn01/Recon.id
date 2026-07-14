import { parseListingFilters, type ListingFilters } from "./listing-filter";
import { collectionCategories, type FeedScope } from "./listings";
import { parseListingSort, type ListingSort } from "./listing-sort";
import { type ListingFeedInput } from "~/server/listings/feed-input";

export type ListingFeedQueryInput = Omit<ListingFeedInput, "cursor">;

export function buildListingFeedInput(
  scope: FeedScope,
  filters: ListingFilters,
  query: string,
  sort: ListingSort,
): ListingFeedQueryInput {
  const platforms =
    scope.type === "platform" ? [scope.slug] : filters.platforms;
  const categories =
    scope.type === "collection" ? collectionCategories(scope.slug) : [];
  const normalizedQuery = query.trim().slice(0, 80);

  return {
    limit: 12,
    ...(platforms.length > 0 ? { platforms } : {}),
    ...(filters.statuses.length > 0 ? { statuses: filters.statuses } : {}),
    ...(categories.length > 0 ? { categories } : {}),
    ...(filters.locations.length > 0 ? { locations: filters.locations } : {}),
    ...(filters.conditions.length > 0
      ? { conditions: filters.conditions }
      : {}),
    ...(filters.minPrice !== null ? { minPrice: filters.minPrice } : {}),
    ...(filters.maxPrice !== null ? { maxPrice: filters.maxPrice } : {}),
    ...(normalizedQuery ? { q: normalizedQuery } : {}),
    ...(sort !== "newest" ? { sort } : {}),
  };
}

export function buildListingFeedInputFromSearchParams(
  scope: FeedScope,
  params: URLSearchParams,
) {
  return buildListingFeedInput(
    scope,
    parseListingFilters(params),
    params.get("q") ?? "",
    parseListingSort(params.get("sort")),
  );
}

export function toUrlSearchParams(
  values: Record<string, string | string[] | undefined>,
) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (Array.isArray(value)) {
      for (const item of value) params.append(key, item);
    } else if (value !== undefined) {
      params.set(key, value);
    }
  }
  return params;
}
