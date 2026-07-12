import { type Prisma } from "../../../generated/prisma";

export const listingFeedSelect = {
  id: true,
  platform: true,
  sourceUrl: true,
  externalId: true,
  title: true,
  description: true,
  category: true,
  brand: true,
  price: true,
  locationTexts: true,
  conditionText: true,
  sellerName: true,
  status: true,
  postedAt: true,
  firstFetchedAt: true,
  lastFetchedAt: true,
  images: {
    select: {
      sourceUrl: true,
      position: true,
      altText: true,
    },
    orderBy: {
      position: "asc",
    },
  },
} satisfies Prisma.ListingSelect;

export type ListingFeedRecord = Prisma.ListingGetPayload<{
  select: typeof listingFeedSelect;
}>;

const platformValues = {
  REDDIT: "reddit",
  INSTAGRAM: "instagram",
  FACEBOOK: "facebook",
} as const;

const statusValues = {
  AVAILABLE: "available",
  UNKNOWN: "unknown",
  SOLD: "sold",
} as const;

export function toListingDto(listing: ListingFeedRecord) {
  if (!isSafeHttpsUrl(listing.sourceUrl)) {
    throw new Error("listing source URL must use HTTPS");
  }

  return {
    id: listing.id,
    platform: platformValues[listing.platform],
    sourceUrl: listing.sourceUrl,
    externalId: listing.externalId,
    title: listing.title,
    description: listing.description,
    category: listing.category,
    brand: listing.brand,
    price: listing.price,
    currency: "IDR" as const,
    locationTexts: listing.locationTexts,
    conditionText: listing.conditionText,
    sellerName: listing.sellerName,
    status: statusValues[listing.status],
    postedAt: listing.postedAt,
    firstFetchedAt: listing.firstFetchedAt,
    lastFetchedAt: listing.lastFetchedAt,
    images: [...listing.images]
      .filter((image) => isSafeHttpsUrl(image.sourceUrl))
      .sort((left, right) => left.position - right.position)
      .map((image) => ({
        sourceUrl: image.sourceUrl,
        position: image.position,
        altText: image.altText,
      })),
  };
}

function isSafeHttpsUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.username === "" && url.password === "";
  } catch {
    return false;
  }
}
