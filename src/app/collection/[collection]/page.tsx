import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ReconFeedPage } from "~/components/recon-feed-page";
import { collections } from "~/data/listings";

type CollectionPageProps = {
  params: Promise<{ collection: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({
  params,
  searchParams,
}: CollectionPageProps): Promise<Metadata> {
  const { collection } = await params;
  const matched = collections.find((item) => item.slug === collection);
  if (!matched) return {};

  const hasQueryParameters = Object.values(await searchParams).some(
    (value) => value !== undefined,
  );
  const path = `/collection/${matched.slug}`;
  const description =
    matched.slug === "all"
      ? "Lihat temuan terbaru komputer, komponen, dan gaming gear preloved dari berbagai platform."
      : `Temukan listing ${matched.label.toLowerCase()} preloved terbaru dari berbagai platform di RECON.`;

  return {
    title:
      matched.slug === "all" ? "Temuan terbaru" : `${matched.label} preloved`,
    description,
    alternates: { canonical: path },
    openGraph: { title: `${matched.label} - RECON`, description, url: path },
    robots: hasQueryParameters
      ? { index: false, follow: true }
      : { index: true, follow: true },
  };
}

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
