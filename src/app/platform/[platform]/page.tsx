import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ReconFeed } from "~/components/recon-feed";
import { platformMeta, type ListingPlatform } from "~/data/dummy-listings";

type PlatformPageProps = {
  params: Promise<{ platform: string }>;
};

export default async function PlatformPage({ params }: PlatformPageProps) {
  const { platform } = await params;

  if (!(platform in platformMeta)) notFound();

  return (
    <Suspense fallback={<div className="page-loading">Menyusun temuan…</div>}>
      <ReconFeed
        scope={{ type: "platform", slug: platform as ListingPlatform }}
      />
    </Suspense>
  );
}
