import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ReconFeedPage } from "~/components/recon-feed-page";
import { platformMeta, type ListingPlatform } from "~/data/listings";

type PlatformPageProps = {
  params: Promise<{ platform: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function PlatformPage({
  params,
  searchParams,
}: PlatformPageProps) {
  const { platform } = await params;

  if (!(platform in platformMeta)) notFound();

  return (
    <Suspense fallback={<div className="page-loading">Menyusun temuan…</div>}>
      <ReconFeedPage
        scope={{ type: "platform", slug: platform as ListingPlatform }}
        searchParams={searchParams}
      />
    </Suspense>
  );
}
