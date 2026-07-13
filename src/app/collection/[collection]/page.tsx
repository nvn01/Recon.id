import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ReconFeed } from "~/components/recon-feed";
import { collections } from "~/data/dummy-listings";

type CollectionPageProps = {
  params: Promise<{ collection: string }>;
};

export default async function CollectionPage({ params }: CollectionPageProps) {
  const { collection } = await params;

  if (!collections.some((item) => item.slug === collection)) notFound();

  return (
    <Suspense fallback={<div className="page-loading">Menyusun temuan…</div>}>
      <ReconFeed scope={{ type: "collection", slug: collection }} />
    </Suspense>
  );
}
