export const manualListingRefreshQueryOptions = {
  refetchOnReconnect: false,
  refetchOnWindowFocus: false,
  staleTime: Infinity,
} as const;

export const listingVersionQueryOptions = {
  refetchInterval: 30 * 1000,
  refetchIntervalInBackground: false,
  refetchOnReconnect: true,
  refetchOnWindowFocus: true,
  retry: 1,
  staleTime: 0,
} as const;

export type ListingVersionSnapshot = {
  revision: string;
  totalCount: number;
};

export type ListingRefreshState = {
  current: ListingVersionSnapshot | null;
  acknowledged: ListingVersionSnapshot | null;
  unseenCount: number;
};

const emptyRefreshState: ListingRefreshState = {
  current: null,
  acknowledged: null,
  unseenCount: 0,
};

function getUnseenCount(
  acknowledged: ListingVersionSnapshot | null,
  current: ListingVersionSnapshot | null,
) {
  if (!acknowledged || !current || acknowledged.revision === current.revision) {
    return 0;
  }
  return countUnseenListings(acknowledged.totalCount, current.totalCount);
}

export function createListingRefreshStore() {
  let state = emptyRefreshState;
  const listeners = new Set<() => void>();

  function publish(next: ListingRefreshState) {
    if (
      state.current === next.current &&
      state.acknowledged === next.acknowledged &&
      state.unseenCount === next.unseenCount
    ) {
      return;
    }
    state = next;
    for (const listener of listeners) listener();
  }

  return {
    getSnapshot: () => state,
    getServerSnapshot: () => emptyRefreshState,
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    observe(current: ListingVersionSnapshot) {
      const acknowledged = state.acknowledged ?? current;
      publish({
        current,
        acknowledged,
        unseenCount: getUnseenCount(acknowledged, current),
      });
    },
    acknowledge(current = state.current) {
      if (!current) return;
      publish({
        current,
        acknowledged: current,
        unseenCount: 0,
      });
    },
  };
}

export const listingRefreshStore = createListingRefreshStore();

export function hasNewListingRevision(
  seenRevision: string | null,
  currentRevision: string | null,
): boolean {
  return Boolean(
    seenRevision && currentRevision && seenRevision !== currentRevision,
  );
}

export function countUnseenListings(
  seenCount: number | null,
  currentCount: number,
): number {
  return Math.max(0, currentCount - (seenCount ?? currentCount));
}
