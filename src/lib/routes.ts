export const allListingsPath = "/";

export function collectionPath(slug: string) {
  return slug === "all" ? allListingsPath : `/collection/${slug}`;
}
