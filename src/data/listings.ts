import { type ListingDto } from "~/server/listings/listing-dto";

export type Listing = ListingDto;
export type ListingPlatform = Listing["platform"];
export type ListingStatus = Listing["status"];

export type FeedScope =
  | { type: "collection"; slug: string }
  | { type: "platform"; slug: ListingPlatform };

export const collections = [
  { slug: "all", label: "Semua", mark: "00", categories: [] },
  { slug: "laptop", label: "Laptop", mark: "LP", categories: ["Laptop"] },
  { slug: "gpu", label: "GPU", mark: "GX", categories: ["GPU"] },
  {
    slug: "pc-build",
    label: "PC & Komponen",
    mark: "PC",
    categories: [
      "Desktop PC",
      "PC Case",
      "CPU",
      "RAM",
      "Storage",
      "Motherboard",
      "Power Supply",
    ],
  },
  {
    slug: "peripheral",
    label: "Periferal",
    mark: "PR",
    categories: ["Keyboard", "Mouse", "Peripheral", "Audio", "Network Adapter"],
  },
  { slug: "monitor", label: "Monitor", mark: "MN", categories: ["Monitor"] },
  {
    slug: "gaming",
    label: "Gaming",
    mark: "GM",
    categories: ["Game Console", "Game", "Controller", "Handheld PC"],
  },
  {
    slug: "smartphone",
    label: "Ponsel",
    mark: "PH",
    categories: ["Smartphone"],
  },
] as const;

export const listingPlatforms = [
  "instagram",
  "facebook",
  "reddit",
] as const satisfies readonly ListingPlatform[];

export const listingStatuses = [
  "available",
  "unknown",
  "sold",
] as const satisfies readonly ListingStatus[];

export const platformMeta: Record<
  ListingPlatform,
  { label: string; short: string; accent: string; description: string }
> = {
  instagram: {
    label: "Instagram",
    short: "IG",
    accent: "coral",
    description: "Listing dari akun jual-beli dan toko preloved yang dipantau.",
  },
  facebook: {
    label: "Facebook",
    short: "FB",
    accent: "blue",
    description: "Temuan Marketplace dari penjual publik di berbagai kota.",
  },
  reddit: {
    label: "Reddit",
    short: "R/",
    accent: "orange",
    description: "Post WTS komputer dan periferal dari komunitas Indonesia.",
  },
};

export const statusMeta: Record<ListingStatus, { label: string }> = {
  available: { label: "Tersedia" },
  unknown: { label: "Perlu cek" },
  sold: { label: "Terjual" },
};

export function collectionCategories(slug: string): string[] {
  const collection = collections.find((item) => item.slug === slug);
  return collection ? [...collection.categories] : [];
}

export function formatRupiah(value: number | null) {
  if (value === null) return "Harga tidak dicantumkan";

  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatListedAt(value: Date, now = new Date()) {
  const elapsedMs = Math.max(0, now.getTime() - value.getTime());
  const minutes = Math.floor(elapsedMs / 60_000);
  if (minutes < 1) return "Baru saja";
  if (minutes < 60) return `${minutes} menit lalu`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} jam lalu`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} hari lalu`;

  return new Intl.DateTimeFormat("id-ID", {
    day: "numeric",
    month: "short",
    year: value.getFullYear() === now.getFullYear() ? undefined : "numeric",
  }).format(value);
}
