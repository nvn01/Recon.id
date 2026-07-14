import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";

import { ReconHeader } from "~/components/recon-header";
import {
  collections,
  dummyListings,
  formatRupiah,
} from "~/data/dummy-listings";

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
};

const categoryCards = collections.flatMap((collection) => {
  if (collection.slug === "all") return [];

  const listings = dummyListings.filter(
    (listing) => listing.category === collection.slug,
  );
  const cover =
    listings.find((listing) => listing.status !== "sold") ?? listings[0];

  if (!cover) return [];

  const prices = listings.flatMap((listing) =>
    listing.price === null ? [] : [listing.price],
  );

  return [
    {
      ...collection,
      cover,
      count: listings.length,
      description: categoryDescriptions[collection.slug],
      lowestPrice: prices.length > 0 ? Math.min(...prices) : null,
    },
  ];
});

export default function CollectionDirectoryPage() {
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
              <Image
                src={category.cover.imageUrl}
                alt=""
                fill
                priority={index < 2}
                sizes="(max-width: 760px) calc(100vw - 24px), (max-width: 1100px) 50vw, 60vw"
              />
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
