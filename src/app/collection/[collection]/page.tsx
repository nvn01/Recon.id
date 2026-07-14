import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ReconFeedPage } from "~/components/recon-feed-page";
import { collections } from "~/data/listings";

type CollectionPageProps = {
  params: Promise<{ collection: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function CollectionPage({
  params,
  searchParams,
}: CollectionPageProps) {
  const { collection } = await params;

  if (!collections.some((item) => item.slug === collection)) notFound();

  return (
    <Suspense fallback={<div className="page-loading">Menyusun temuan…</div>}>
      <ReconFeedPage
        scope={{ type: "collection", slug: collection }}
        searchParams={searchParams}
      />
    </Suspense>
  );
}
