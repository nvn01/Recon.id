import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";

import { ReconHeader } from "~/components/recon-header";
import { collections, formatRupiah } from "~/data/listings";
import { api } from "~/trpc/server";

export const metadata: Metadata = {
  title: "Koleksi",
  description: "Jelajahi listing RECON berdasarkan kategori barang.",
};

type CategorySlug = Exclude<(typeof collections)[number]["slug"], "all">;

const categoryDescriptions: Record<CategorySlug, string> = {
  laptop: "Laptop kerja, ultrabook, dan mesin gaming portabel.",
  gpu: "Kartu grafis untuk gaming, render, dan upgrade berikutnya.",
  "pc-build": "PC rakitan lengkap, dari compact build sampai workstation.",
  peripheral: "Keyboard, audio, mouse, dan aksesori untuk meja kerja.",
  monitor: "Monitor tunggal, ultrawide, dan paket setup layar.",
  gaming: "Konsol, handheld, dan gear untuk ruang bermain.",
  smartphone: "Ponsel bekas dan perangkat mobile yang baru ditemukan.",
};

const categoryCovers: Record<
  CategorySlug,
  { desktop: string; mobile: string }
> = {
  laptop: {
    desktop: "/collection-covers/laptop-Ivq2PJHUkOA-desktop.webp",
    mobile: "/collection-covers/laptop-Ivq2PJHUkOA-mobile.webp",
  },
  gpu: {
    desktop: "/collection-covers/gpu-3UAiwOgoSnE-desktop.webp",
    mobile: "/collection-covers/gpu-3UAiwOgoSnE-mobile.webp",
  },
  "pc-build": {
    desktop: "/collection-covers/pc-build-rst3YOh6LXA-desktop.webp",
    mobile: "/collection-covers/pc-build-rst3YOh6LXA-mobile.webp",
  },
  peripheral: {
    desktop: "/collection-covers/peripheral-O28lxHLRiyA-desktop.webp",
    mobile: "/collection-covers/peripheral-O28lxHLRiyA-mobile.webp",
  },
  monitor: {
    desktop: "/collection-covers/monitor-tkRrmYoN2to-desktop.webp",
    mobile: "/collection-covers/monitor-tkRrmYoN2to-mobile.webp",
  },
  gaming: {
    desktop: "/collection-covers/gaming-rZDBOGPHU7w-desktop.webp",
    mobile: "/collection-covers/gaming-rZDBOGPHU7w-mobile.webp",
  },
  smartphone: {
    desktop: "/collection-covers/smartphone-z4-5V8s5sVk-desktop.webp",
    mobile: "/collection-covers/smartphone-z4-5V8s5sVk-mobile.webp",
  },
};

export default async function CollectionDirectoryPage() {
  const facets = await api.listings.facets();
  const categoryCards = collections.flatMap((collection) => {
    if (collection.slug === "all") return [];

    const categoryValues: readonly string[] = collection.categories;
    const matching = facets.categories.filter((category) =>
      categoryValues.includes(category.value),
    );
    const prices = matching.flatMap((category) =>
      category.minPrice === null ? [] : [category.minPrice],
    );
    return [
      {
        ...collection,
        cover: categoryCovers[collection.slug],
        count: matching.reduce((total, category) => total + category.count, 0),
        description: categoryDescriptions[collection.slug],
        lowestPrice: prices.length > 0 ? Math.min(...prices) : null,
      },
    ];
  });
  return (
    <div className="app-shell">
      <Suspense fallback={<div className="header-placeholder" />}>
        <ReconHeader />
      </Suspense>

      <main className="collection-directory-main">
        <section className="collection-directory-hero">
          <div>
            <h1>Mau cari apa?</h1>
            <p>
              Pilih kategori untuk membuka listing terbaru dari semua sumber.
            </p>
          </div>
          <Link className="collection-all-link" href="/collection/all">
            Lihat semua listing
          </Link>
        </section>

        <div className="collection-directory-grid">
          {categoryCards.map((category, index) => (
            <Link
              key={category.slug}
              href={`/collection/${category.slug}`}
              className={`collection-directory-card collection-directory-${category.slug}`}
            >
              <picture className="collection-card-media">
                <source
                  media="(max-width: 760px)"
                  srcSet={category.cover.mobile}
                  type="image/webp"
                />
                <Image
                  src={category.cover.desktop}
                  alt=""
                  fill
                  priority={index < 2}
                  unoptimized
                  sizes="(max-width: 760px) calc(100vw - 24px), (max-width: 1100px) 50vw, 60vw"
                />
              </picture>
              <span className="collection-card-scrim" aria-hidden="true" />
              <div className="collection-card-copy">
                <div>
                  <h2>{category.label}</h2>
                  <p>{category.description}</p>
                </div>
                <div className="collection-card-facts">
                  <span>{category.count} listing</span>
                  <span>
                    {category.lowestPrice === null
                      ? "Harga beragam"
                      : `Mulai ${formatRupiah(category.lowestPrice)}`}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>

        <div className="collection-directory-footer">
          <p>Lebih nyaman mulai dari sumber?</p>
          <Link href="/platform">Jelajahi platform</Link>
        </div>
      </main>
    </div>
  );
}
