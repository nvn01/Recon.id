export const manualListingRefreshQueryOptions = {
  refetchOnReconnect: false,
  refetchOnWindowFocus: false,
  staleTime: Infinity,
} as const;

export const automaticListingRefreshQueryOptions = {
  refetchOnMount: "always",
  refetchOnReconnect: true,
  refetchOnWindowFocus: true,
  staleTime: 0,
} as const;

export const listingVersionQueryOptions = {
  refetchInterval: 30 * 1000,
  refetchIntervalInBackground: false,
  refetchOnReconnect: true,
  refetchOnWindowFocus: true,
  retry: 1,
  staleTime: 0,
} as const;

export function hasNewListingRevision(
  seenRevision: string | null,
  currentRevision: string | null,
): boolean {
  return Boolean(
    seenRevision && currentRevision && seenRevision !== currentRevision,
  );
}
