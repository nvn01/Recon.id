import { ReconFeed } from "~/components/recon-feed";
import {
  buildListingFeedInputFromSearchParams,
  toUrlSearchParams,
} from "~/data/listing-query";
import { type FeedScope } from "~/data/listings";
import { api, HydrateClient } from "~/trpc/server";

type SearchParamRecord = Record<string, string | string[] | undefined>;

export async function ReconFeedPage({
  scope,
  searchParams,
}: {
  scope: FeedScope;
  searchParams: Promise<SearchParamRecord>;
}) {
  const params = toUrlSearchParams(await searchParams);
  const feedInput = buildListingFeedInputFromSearchParams(scope, params);

  await Promise.all([
    api.listings.feed.prefetchInfinite(feedInput),
    api.listings.facets.prefetch(),
    api.listings.version.prefetch(),
  ]);

  return (
    <HydrateClient>
      <ReconFeed scope={scope} />
    </HydrateClient>
  );
}
