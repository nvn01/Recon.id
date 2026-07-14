export const manualListingRefreshQueryOptions = {
  refetchOnReconnect: false,
  refetchOnWindowFocus: false,
  staleTime: Infinity,
} as const;

export function hasUnseenListingRevision(
  seenRevision: string | null,
  currentRevision: string | null,
): boolean {
  return Boolean(
    seenRevision && currentRevision && seenRevision !== currentRevision,
  );
}
