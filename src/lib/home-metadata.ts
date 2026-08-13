import type { Metadata } from "next";

import { siteConfig } from "~/lib/site";

type SearchParamRecord = Record<string, string | string[] | undefined>;

export function buildHomeMetadata(searchParams: SearchParamRecord): Metadata {
  const hasQueryParameters = Object.values(searchParams).some(
    (value) => value !== undefined,
  );

  return {
    title: { absolute: siteConfig.title },
    description: siteConfig.description,
    alternates: { canonical: siteConfig.homePath },
    openGraph: {
      siteName: siteConfig.name,
      title: siteConfig.title,
      description: siteConfig.description,
      url: siteConfig.homePath,
    },
    robots: hasQueryParameters
      ? { index: false, follow: true }
      : { index: true, follow: true },
  };
}
