"use client";

import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { ReconHeader } from "~/components/recon-header";
import {
  collections,
  dummyListings,
  formatRupiah,
  platformMeta,
  type DummyListing,
  type ListingPlatform,
  type ListingStatus,
} from "~/data/dummy-listings";

type FeedScope =
  | { type: "collection"; slug: string }
  | { type: "platform"; slug: ListingPlatform };

type ReconFeedProps = {
  scope: FeedScope;
};

const statusMeta: Record<ListingStatus, { label: string; className: string }> = {
  available: { label: "Tersedia", className: "is-available" },
  unknown: { label: "Perlu cek", className: "is-unknown" },
  sold: { label: "Terjual", className: "is-sold" },
};

function ArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 17 17 7M8 7h9v9" />
    </svg>
  );
}

function SlidersIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7h10m4 0h2M4 17h2m4 0h10M14 5v4M6 15v4" />
    </svg>
  );
}

function SortIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 7h14M8 12h8m-5 5h2" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6 6 12 12M18 6 6 18" />
    </svg>
  );
}

function withQuery(path: string, params: URLSearchParams) {
  const value = params.toString();
  return `${path}${value ? `?${value}` : ""}`;
}

function clearKey(params: URLSearchParams, key: string) {
  const next = new URLSearchParams(params.toString());
  next.delete(key);
  return next;
}

function titleForScope(scope: FeedScope) {
  if (scope.type === "platform") {
    return `${platformMeta[scope.slug].label}, satu feed.`;
  }

  if (scope.slug === "all") return "Barang bagus muncul sebentar.";

  return `${collections.find((item) => item.slug === scope.slug)?.label ?? "Koleksi"} yang baru ditemukan.`;
}

function PlatformBadge({ platform }: { platform: ListingPlatform }) {
  const meta = platformMeta[platform];
  return (
    <span className={`platform-badge platform-${meta.accent}`}>
      <span aria-hidden="true">{meta.short}</span>
      {meta.label}
    </span>
  );
}

function ListingCard({
  listing,
  priority,
  onOpen,
}: {
  listing: DummyListing;
  priority?: boolean;
  onOpen: (listing: DummyListing) => void;
}) {
  const status = statusMeta[listing.status];
  const images = [listing.imageUrl, ...(listing.previewImageUrls ?? [])];
  const [activeImage, setActiveImage] = useState(0);
  const intentTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const carouselTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopPreview(reset = true) {
    if (intentTimer.current) clearTimeout(intentTimer.current);
    if (carouselTimer.current) clearInterval(carouselTimer.current);
    intentTimer.current = null;
    carouselTimer.current = null;
    if (reset) setActiveImage(0);
  }

  function startPreview(event: React.PointerEvent<HTMLButtonElement>) {
    if (
      event.pointerType !== "mouse" ||
      images.length < 2 ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return;
    }

    stopPreview(false);
    intentTimer.current = setTimeout(() => {
      setActiveImage(1);
      carouselTimer.current = setInterval(() => {
        setActiveImage((current) => (current + 1) % images.length);
      }, 400);
    }, 180);
  }

  useEffect(
    () => () => {
      if (intentTimer.current) clearTimeout(intentTimer.current);
      if (carouselTimer.current) clearInterval(carouselTimer.current);
    },
    [],
  );

  return (
    <article className={`listing-card ${listing.status === "sold" ? "card-sold" : ""}`}>
      <button
        type="button"
        className={`listing-image image-${listing.imageAspect}`}
        onClick={() => onOpen(listing)}
        onPointerEnter={startPreview}
        onPointerLeave={() => stopPreview()}
        onPointerCancel={() => stopPreview()}
      >
        <span className="carousel-media" aria-hidden="true">
          {images.map((imageUrl, index) => (
            <Image
              key={imageUrl}
              className={`carousel-frame ${index === activeImage ? "is-active" : ""}`}
              src={imageUrl}
              alt=""
              fill
              priority={priority && index === 0}
              sizes="(max-width: 520px) 48vw, (max-width: 900px) 32vw, (max-width: 1280px) 25vw, 20vw"
            />
          ))}
        </span>
        <span className="image-price">{formatRupiah(listing.price)}</span>
        <span className={`status-pill ${status.className}`}>
          {status.label}
        </span>
        {images.length > 1 ? (
          <span className="carousel-dots" aria-hidden="true">
            {images.map((imageUrl, index) => (
              <i key={imageUrl} className={index === activeImage ? "active" : undefined} />
            ))}
          </span>
        ) : null}
        <span className="quick-view">
          Lihat detail <ArrowIcon />
        </span>
        <span className="sr-only">{listing.title}</span>
      </button>

      <div className="listing-copy">
        <div className="listing-meta-row">
          <PlatformBadge platform={listing.platform} />
          <span>{listing.postedLabel}</span>
        </div>
        <button
          type="button"
          className="listing-title"
          onClick={() => onOpen(listing)}
        >
          {listing.title}
        </button>
        <p className="listing-place">{listing.location}</p>
      </div>
    </article>
  );
}

function ListingDialog({
  listing,
  onClose,
}: {
  listing: DummyListing | null;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;

    if (listing && !dialog.open) {
      dialog.showModal();
      dialog.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    } else if (!listing && dialog.open) {
      dialog.close();
    }
  }, [listing]);

  return (
    <dialog
      ref={ref}
      className="listing-dialog"
      onClose={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      {listing ? (
        <div className="dialog-card">
          <button
            type="button"
            className="dialog-close"
            onClick={onClose}
            aria-label="Tutup detail listing"
            data-autofocus
          >
            <CloseIcon />
          </button>
          <div className={`dialog-image image-${listing.imageAspect}`}>
            <Image
              src={listing.imageUrl}
              alt={listing.imageAlt}
              fill
              sizes="(max-width: 760px) 100vw, 54vw"
            />
          </div>
          <div className="dialog-copy">
            <div className="dialog-topline">
              <PlatformBadge platform={listing.platform} />
              <span>{listing.postedLabel}</span>
            </div>
            <h2>{listing.title}</h2>
            <p className="dialog-price">{formatRupiah(listing.price)}</p>
            <p className="dialog-description">{listing.description}</p>
            <dl className="dialog-facts">
              <div>
                <dt>Kondisi</dt>
                <dd>{listing.condition}</dd>
              </div>
              <div>
                <dt>Lokasi</dt>
                <dd>{listing.location}</dd>
              </div>
              <div>
                <dt>Penjual</dt>
                <dd>{listing.seller}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>{statusMeta[listing.status].label}</dd>
              </div>
            </dl>
            <div className="dialog-actions">
              <a
                className="primary-action"
                href={listing.imagePageUrl}
                target="_blank"
                rel="noreferrer"
              >
                Sumber foto demo <ArrowIcon />
              </a>
              <p>
                Data masih dummy. Tombol listing asli akan aktif saat feed API dipasang.
              </p>
            </div>
          </div>
        </div>
      ) : null}
    </dialog>
  );
}

export function ReconFeed({ scope }: ReconFeedProps) {
  const searchParams = useSearchParams();
  const [visibleCount, setVisibleCount] = useState(12);
  const [selectedListing, setSelectedListing] = useState<DummyListing | null>(null);
  const query = (searchParams.get("q") ?? "").trim().toLowerCase();
  const selectedPlatforms = searchParams.getAll("platform") as ListingPlatform[];
  const selectedStatuses = searchParams.getAll("status") as ListingStatus[];

  const filteredListings = useMemo(() => {
    return dummyListings.filter((listing) => {
      const categoryMatches =
        scope.type !== "collection" ||
        scope.slug === "all" ||
        listing.category === scope.slug;
      const platformMatches =
        scope.type === "platform"
          ? listing.platform === scope.slug
          : selectedPlatforms.length === 0 ||
            selectedPlatforms.includes(listing.platform);
      const statusMatches =
        selectedStatuses.length === 0 || selectedStatuses.includes(listing.status);
      const haystack = [
        listing.title,
        listing.description,
        listing.brand,
        listing.location,
        ...listing.tags,
      ]
        .join(" ")
        .toLowerCase();
      const queryMatches = !query || haystack.includes(query);

      return categoryMatches && platformMatches && statusMatches && queryMatches;
    });
  }, [query, scope, selectedPlatforms, selectedStatuses]);

  const baseParams = new URLSearchParams(searchParams.toString());

  function collectionHref(slug: string) {
    const next = new URLSearchParams(baseParams.toString());
    if (scope.type === "platform") {
      next.delete("platform");
      if (slug === "all") return withQuery(`/platform/${scope.slug}`, next);
      next.append("platform", scope.slug);
    } else if (slug === "all" && selectedPlatforms.length === 1) {
      next.delete("platform");
      return withQuery(`/platform/${selectedPlatforms[0]}`, next);
    }

    return withQuery(`/collection/${slug}`, next);
  }

  function platformHref(platform: ListingPlatform | "all") {
    const next = clearKey(baseParams, "platform");
    if (platform === "all") {
      const collection = scope.type === "collection" ? scope.slug : "all";
      return withQuery(`/collection/${collection}`, next);
    }

    if (scope.type === "collection" && scope.slug !== "all") {
      next.append("platform", platform);
      return withQuery(`/collection/${scope.slug}`, next);
    }

    return withQuery(`/platform/${platform}`, next);
  }

  function statusHref(status: ListingStatus | "all") {
    const next = clearKey(baseParams, "status");
    if (status !== "all") next.append("status", status);
    const path =
      scope.type === "platform"
        ? `/platform/${scope.slug}`
        : `/collection/${scope.slug}`;
    return withQuery(path, next);
  }

  const currentPlatform = scope.type === "platform" ? scope.slug : selectedPlatforms[0];
  const currentStatus = selectedStatuses.length === 1 ? selectedStatuses[0] : undefined;
  const shownListings = filteredListings.slice(0, visibleCount);

  return (
    <div className="app-shell">
      <ReconHeader>
        <div className="header-controls">
          <nav className="collection-rail" aria-label="Koleksi produk">
            {collections.map((collection) => {
              const active =
                scope.type === "collection" && scope.slug === collection.slug;
              return (
                <Link
                  key={collection.slug}
                  href={collectionHref(collection.slug)}
                  className={active ? "active" : undefined}
                  aria-current={active ? "page" : undefined}
                >
                  {collection.label}
                </Link>
              );
            })}
          </nav>

          <div className="header-filter-actions">
            <div className="platform-filters" aria-label="Filter platform">
            <Link
              href={platformHref("all")}
              className={!currentPlatform ? "active" : undefined}
            >
              Semua sumber
            </Link>
            {(Object.keys(platformMeta) as ListingPlatform[]).map((platform) => (
              <Link
                key={platform}
                href={platformHref(platform)}
                className={currentPlatform === platform ? "active" : undefined}
              >
                {platformMeta[platform].label}
              </Link>
            ))}
            </div>

            <details className="filter-menu">
              <summary>
                <SlidersIcon />
                Filter
                {currentStatus ? <span className="filter-count">1</span> : null}
              </summary>
              <div className="filter-popover">
                <p>Status listing</p>
                <Link
                  href={statusHref("all")}
                  className={!currentStatus ? "active" : undefined}
                >
                  Semua status
                </Link>
                {(Object.keys(statusMeta) as ListingStatus[]).map((status) => (
                  <Link
                    key={status}
                    href={statusHref(status)}
                    className={currentStatus === status ? "active" : undefined}
                  >
                    {statusMeta[status].label}
                  </Link>
                ))}
                <div className="sort-note">
                  <span>Urutan</span>
                  Tersedia dulu, lalu terbaru
                </div>
              </div>
            </details>
            <span className="sort-chip"><SortIcon /> Terbaru dulu</span>
          </div>
        </div>
      </ReconHeader>

      <main className="feed-main">
        <h1 className="sr-only">{titleForScope(scope)}</h1>
        <p className="sr-only" aria-live="polite">
          {filteredListings.length} listing demo cocok
        </p>

        {query ? (
          <div className="query-banner">
            <p>
              Hasil pencarian untuk <strong>“{query}”</strong>
            </p>
            <Link href={withQuery(
              scope.type === "platform"
                ? `/platform/${scope.slug}`
                : `/collection/${scope.slug}`,
              clearKey(baseParams, "q"),
            )}>
              Hapus pencarian
            </Link>
          </div>
        ) : null}

        {shownListings.length > 0 ? (
          <div className="masonry-feed">
            {shownListings.map((listing, index) => (
              <ListingCard
                key={listing.id}
                listing={listing}
                priority={index === 0}
                onOpen={setSelectedListing}
              />
            ))}
          </div>
        ) : (
          <section className="empty-state">
            <span>NO SIGNAL</span>
            <h2>Belum ada listing yang cocok.</h2>
            <p>Coba hapus pencarian atau buka kembali semua sumber.</p>
            <Link href="/collection/all">Kembali ke semua listing</Link>
          </section>
        )}

        {visibleCount < filteredListings.length ? (
          <div className="load-more-wrap">
            <button type="button" onClick={() => setVisibleCount((count) => count + 6)}>
              Muat temuan berikutnya
              <span>{filteredListings.length - visibleCount} tersisa</span>
            </button>
          </div>
        ) : shownListings.length > 0 ? (
          <p className="feed-end">Semua listing demo sudah ditampilkan.</p>
        ) : null}

        <footer className="feed-footer">
          <p>RECON / PUBLIC LISTING MONITOR</p>
          <p>Foto demo bersumber dari Unsplash.</p>
        </footer>
      </main>

      <ListingDialog listing={selectedListing} onClose={() => setSelectedListing(null)} />
    </div>
  );
}
