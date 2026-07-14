import Link from "next/link";
import { Suspense } from "react";

import { ReconHeader } from "~/components/recon-header";
import {
  listingPlatforms,
  platformMeta,
  type ListingPlatform,
} from "~/data/listings";

export default function PlatformDirectoryPage() {
  return (
    <div className="app-shell">
      <Suspense fallback={<div className="header-placeholder" />}>
        <ReconHeader />
      </Suspense>
      <main className="platform-main">
        <div className="platform-heading">
          <p className="eyebrow">Pilih sumber / 03 aktif</p>
          <h1>Satu barang, banyak tempat mencarinya.</h1>
          <p>
            Buka satu platform untuk melihat listing yang RECON temukan dari
            sumber itu saja.
          </p>
        </div>
        <div className="platform-grid">
          {listingPlatforms.map((platform: ListingPlatform, index) => {
            const meta = platformMeta[platform];
            return (
              <Link
                key={platform}
                href={`/platform/${platform}`}
                className={`platform-directory-card platform-${meta.accent}`}
              >
                <span className="directory-index">0{index + 1}</span>
                <div className="directory-mark">{meta.short}</div>
                <div>
                  <h2>{meta.label}</h2>
                  <p>{meta.description}</p>
                </div>
                <span className="directory-action">Buka feed ↗</span>
              </Link>
            );
          })}
        </div>
        <Link className="back-to-feed" href="/collection/all">
          ← Kembali ke semua listing
        </Link>
      </main>
    </div>
  );
}
