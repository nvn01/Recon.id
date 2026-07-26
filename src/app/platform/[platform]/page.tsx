import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ReconFeedPage } from "~/components/recon-feed-page";
import { platformMeta, type ListingPlatform } from "~/data/listings";

type PlatformPageProps = {
  params: Promise<{ platform: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({
  params,
  searchParams,
}: PlatformPageProps): Promise<Metadata> {
  const { platform } = await params;
  if (!(platform in platformMeta)) return {};

  const matched = platformMeta[platform as ListingPlatform];
  const hasQueryParameters = Object.values(await searchParams).some(
    (value) => value !== undefined,
  );
  const path = `/platform/${platform}`;
  const description = `Lihat temuan listing ${matched.label} terbaru yang dirangkum RECON dan selalu periksa posting sumber sebelum bertransaksi.`;

  return {
    title: matched.label,
    description,
    alternates: { canonical: path },
    openGraph: { title: `${matched.label} - RECON`, description, url: path },
    robots: hasQueryParameters
      ? { index: false, follow: true }
      : { index: true, follow: true },
  };
}

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
