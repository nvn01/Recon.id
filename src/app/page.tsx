import type { Metadata } from "next";
import { Suspense } from "react";

import { ReconFeedPage } from "~/components/recon-feed-page";
import { buildHomeMetadata } from "~/lib/home-metadata";

type HomePageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({
  searchParams,
}: HomePageProps): Promise<Metadata> {
  return buildHomeMetadata(await searchParams);
}

export default function Home({ searchParams }: HomePageProps) {
  return (
    <Suspense fallback={<div className="page-loading">Menyusun temuan…</div>}>
      <ReconFeedPage
        scope={{ type: "collection", slug: "all" }}
        searchParams={searchParams}
      />
    </Suspense>
  );
}
