import type { MetadataRoute } from "next";

import { collections, listingPlatforms } from "~/data/listings";
import { absoluteUrl } from "~/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const staticPages = [
    { path: "/collection/all", priority: 1 },
    { path: "/collection", priority: 0.8 },
    { path: "/platform", priority: 0.7 },
    { path: "/cara-kerja", priority: 0.5 },
    { path: "/privacy", priority: 0.4 },
  ];
  const collectionPages = collections
    .filter((collection) => collection.slug !== "all")
    .map((collection) => ({
      path: `/collection/${collection.slug}`,
      priority: 0.8,
    }));
  const platformPages = listingPlatforms.map((platform) => ({
    path: `/platform/${platform}`,
    priority: 0.7,
  }));

  return [...staticPages, ...collectionPages, ...platformPages].map(
    ({ path, priority }) => ({
      url: absoluteUrl(path),
      changeFrequency: path.startsWith("/collection/")
        ? ("hourly" as const)
        : path.startsWith("/platform/")
          ? ("hourly" as const)
          : ("weekly" as const),
      priority,
    }),
  );
}
