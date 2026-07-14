import { type Prisma } from "../../../generated/prisma";

export const listingFeedSelect = {
  id: true,
  platform: true,
  sourceUrl: true,
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
    title: listing.title,
    description: listing.description,
    category: listing.category,
    brand: listing.brand,
    price: normalizePublicPrice(listing.price),
    currency: "IDR" as const,
    locationTexts: listing.locationTexts.flatMap((value) => {
      const location = sanitizePublicLocation(value);
      return location ? [location] : [];
    }),
    conditionText: listing.conditionText,
    sellerName: listing.sellerName,
    status: statusValues[listing.status],
    listedAt: listing.postedAt ?? listing.firstFetchedAt,
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

export type ListingDto = ReturnType<typeof toListingDto>;

export function isSafeHttpsUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return (
      url.protocol === "https:" && url.username === "" && url.password === ""
    );
  } catch {
    return false;
  }
}

export function sanitizePublicLocation(value: string): string | null {
  const location = value.trim();
  if (!location || location.length > 80 || /[\r\n]/.test(location)) {
    return null;
  }
  if (/https?:\/\/|www\.|@/i.test(location) || /\d{6,}/.test(location)) {
    return null;
  }
  return location;
}

export function normalizePublicPrice(value: number | null): number | null {
  return value !== null &&
    value >= 10_000 &&
    value !== 12_345 &&
    value !== 123_456
    ? value
    : null;
}
