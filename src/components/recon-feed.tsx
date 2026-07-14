"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  type CSSProperties,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";

import { ReconHeader } from "~/components/recon-header";
import { RefreshArrowIcon } from "~/components/refresh-arrow-icon";
import { stepCarouselIndex } from "~/data/carousel-navigation";
import {
  hasUnseenListingRevision,
  manualListingRefreshQueryOptions,
} from "~/data/listing-refresh";
import {
  collections,
  formatListedAt,
  formatRupiah,
  platformMeta,
  statusMeta,
  type FeedScope,
  type Listing,
  type ListingPlatform,
} from "~/data/listings";
import {
  countActiveFilterGroups,
  emptyListingFilters,
  parseListingFilters,
  setListingFilterParams,
  type ListingFilters,
} from "~/data/listing-filter";
import { buildListingFeedInput } from "~/data/listing-query";
import {
  distributeAcrossColumns,
  getMasonryColumnCount,
} from "~/data/masonry-layout";
import { api } from "~/trpc/react";

type ReconFeedProps = {
  scope: FeedScope;
};

function ArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 17 17 7M8 7h9v9" />
    </svg>
  );
}

function VerifiedIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path
        className="verified-burst"
        d="M10.07.87a2.89 2.89 0 0 0-4.14 0l-.62.64-.89-.01A2.89 2.89 0 0 0 1.5 4.42l.01.89-.64.62a2.89 2.89 0 0 0 0 4.14l.64.62-.01.89a2.89 2.89 0 0 0 2.92 2.92l.89-.01.62.64a2.89 2.89 0 0 0 4.14 0l.62-.64.89.01a2.89 2.89 0 0 0 2.92-2.92l-.01-.89.64-.62a2.89 2.89 0 0 0 0-4.14l-.64-.62.01-.89a2.89 2.89 0 0 0-2.92-2.92l-.89.01Z"
      />
      <path className="verified-check" d="m4.6 8.15 2.25 2.25 4.6-4.7" />
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

function CarouselArrowIcon({ direction }: { direction: "left" | "right" }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d={direction === "left" ? "m15 5-7 7 7 7" : "m9 5 7 7-7 7"} />
    </svg>
  );
}

function FilterIcon() {
  return (
    <svg className="filter-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 5h16l-6.25 7.1v5.15l-3.5 1.75v-6.9L4 5Z" />
    </svg>
  );
}

function FeedRefreshSpinner() {
  return <RefreshArrowIcon className="feed-refresh-spinner" />;
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

type ListingFilterDraft = Omit<ListingFilters, "minPrice" | "maxPrice"> & {
  minPrice: string;
  maxPrice: string;
};

function filtersToDraft(filters: ListingFilters): ListingFilterDraft {
  return {
    ...filters,
    minPrice: filters.minPrice === null ? "" : String(filters.minPrice),
    maxPrice: filters.maxPrice === null ? "" : String(filters.maxPrice),
  };
}

function toggleFilterValue<T extends string>(values: T[], value: T) {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}

function conditionLabel(condition: string) {
  const label = condition.replace(/^Bekas - /, "");
  return `${label.charAt(0).toUpperCase()}${label.slice(1)}`;
}

function FilterControl({
  filters,
  locationOptions,
  conditionOptions,
  onApply,
  onClear,
}: {
  filters: ListingFilters;
  locationOptions: readonly { value: string; count: number }[];
  conditionOptions: readonly { value: string; count: number }[];
  onApply: (filters: ListingFilters) => void;
  onClear: () => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [draft, setDraft] = useState(() => filtersToDraft(filters));
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const titleId = `${panelId}-title`;
  const errorId = `${panelId}-price-error`;
  const activeCount = countActiveFilterGroups(filters);
  const minPrice = draft.minPrice ? Number(draft.minPrice) : null;
  const maxPrice = draft.maxPrice ? Number(draft.maxPrice) : null;
  const draftActiveCount = countActiveFilterGroups({
    ...draft,
    minPrice,
    maxPrice,
  });
  const priceError =
    minPrice !== null && maxPrice !== null && minPrice > maxPrice
      ? "Harga terendah tidak boleh lebih besar dari harga tertinggi."
      : null;

  useEffect(() => {
    if (!isOpen) return;

    function handleOutsidePointer(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setIsOpen(false);
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setIsOpen(false);
      triggerRef.current?.focus();
    }

    document.addEventListener("pointerdown", handleOutsidePointer);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("pointerdown", handleOutsidePointer);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen]);

  function togglePanel() {
    if (isOpen) {
      setIsOpen(false);
      return;
    }

    setDraft(filtersToDraft(filters));
    setIsOpen(true);
  }

  function closePanel() {
    setIsOpen(false);
    triggerRef.current?.focus();
  }

  function applyFilters() {
    if (priceError) return;

    onApply({
      ...draft,
      minPrice,
      maxPrice,
    });
    closePanel();
  }

  function clearFilters() {
    setDraft(filtersToDraft(emptyListingFilters));
    onClear();
    closePanel();
  }

  function sanitizePrice(value: string) {
    return value.replace(/\D/g, "").slice(0, 12);
  }

  return (
    <div ref={rootRef} className="filter-control" data-open={isOpen}>
      <button
        ref={triggerRef}
        type="button"
        className="filter-trigger"
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        aria-controls={panelId}
        aria-label={`Filter listing${activeCount ? `, ${activeCount} grup aktif` : ""}`}
        onClick={togglePanel}
      >
        <FilterIcon />
        <span className="filter-trigger-label">Filter</span>
        {activeCount ? (
          <span className="filter-count" aria-hidden="true">
            {activeCount}
          </span>
        ) : null}
      </button>

      {isOpen ? (
        <section
          id={panelId}
          className="filter-panel"
          role="dialog"
          aria-modal="false"
          aria-labelledby={titleId}
        >
          <div className="filter-panel-header">
            <h2 id={titleId}>Filter listing</h2>
            <button
              type="button"
              className="filter-close"
              aria-label="Tutup filter"
              onClick={closePanel}
            >
              <CloseIcon />
            </button>
          </div>

          <div className="filter-panel-body">
            <fieldset className="filter-section">
              <legend className="sr-only">Platform</legend>
              <div className="filter-section-heading" aria-hidden="true">
                <span>Platform</span>
                <small>Pilih beberapa</small>
              </div>
              <div className="filter-choice-grid platform-choices">
                {(Object.keys(platformMeta) as ListingPlatform[]).map(
                  (platform) => (
                    <label key={platform} className="filter-choice">
                      <input
                        type="checkbox"
                        checked={draft.platforms.includes(platform)}
                        onChange={() =>
                          setDraft((current) => ({
                            ...current,
                            platforms: toggleFilterValue(
                              current.platforms,
                              platform,
                            ),
                          }))
                        }
                      />
                      <span className="filter-check" aria-hidden="true" />
                      <span>{platformMeta[platform].label}</span>
                    </label>
                  ),
                )}
              </div>
            </fieldset>

            <fieldset className="filter-section">
              <legend className="sr-only">Status</legend>
              <div className="filter-section-heading" aria-hidden="true">
                <span>Status</span>
                <small>Pilih beberapa</small>
              </div>
              <div className="filter-choice-grid status-choices">
                {(
                  Object.keys(statusMeta) as Array<keyof typeof statusMeta>
                ).map((status) => (
                  <label key={status} className="filter-choice">
                    <input
                      type="checkbox"
                      checked={draft.statuses.includes(status)}
                      onChange={() =>
                        setDraft((current) => ({
                          ...current,
                          statuses: toggleFilterValue(current.statuses, status),
                        }))
                      }
                    />
                    <span className="filter-check" aria-hidden="true" />
                    <span>{statusMeta[status].label}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <fieldset className="filter-section price-section">
              <legend className="sr-only">Harga</legend>
              <div className="filter-section-heading" aria-hidden="true">
                <span>Harga</span>
                <small>Rupiah</small>
              </div>
              <div className="price-range">
                <label htmlFor={`${panelId}-min-price`}>
                  <span>Terendah</span>
                  <span className="price-field">
                    <span>Rp</span>
                    <input
                      id={`${panelId}-min-price`}
                      type="text"
                      inputMode="numeric"
                      value={draft.minPrice}
                      placeholder="0"
                      aria-invalid={Boolean(priceError)}
                      aria-describedby={priceError ? errorId : undefined}
                      onChange={(event) =>
                        setDraft((current) => ({
                          ...current,
                          minPrice: sanitizePrice(event.target.value),
                        }))
                      }
                    />
                  </span>
                </label>
                <span className="price-separator" aria-hidden="true" />
                <label htmlFor={`${panelId}-max-price`}>
                  <span>Tertinggi</span>
                  <span className="price-field">
                    <span>Rp</span>
                    <input
                      id={`${panelId}-max-price`}
                      type="text"
                      inputMode="numeric"
                      value={draft.maxPrice}
                      placeholder="Tanpa batas"
                      aria-invalid={Boolean(priceError)}
                      aria-describedby={priceError ? errorId : undefined}
                      onChange={(event) =>
                        setDraft((current) => ({
                          ...current,
                          maxPrice: sanitizePrice(event.target.value),
                        }))
                      }
                    />
                  </span>
                </label>
              </div>
              {priceError ? (
                <p id={errorId} className="filter-error" role="alert">
                  {priceError}
                </p>
              ) : null}
            </fieldset>

            <fieldset className="filter-section">
              <legend className="sr-only">Kondisi</legend>
              <div className="filter-section-heading" aria-hidden="true">
                <span>Kondisi</span>
                <small>Pilih beberapa</small>
              </div>
              <div className="filter-choice-grid condition-choices">
                {conditionOptions.map((condition) => (
                  <label key={condition.value} className="filter-choice">
                    <input
                      type="checkbox"
                      checked={draft.conditions.includes(condition.value)}
                      onChange={() =>
                        setDraft((current) => ({
                          ...current,
                          conditions: toggleFilterValue(
                            current.conditions,
                            condition.value,
                          ),
                        }))
                      }
                    />
                    <span className="filter-check" aria-hidden="true" />
                    <span>{conditionLabel(condition.value)}</span>
                  </label>
                ))}
                {conditionOptions.length === 0 ? (
                  <p className="filter-options-empty">
                    Belum ada kondisi terindeks.
                  </p>
                ) : null}
              </div>
            </fieldset>

            <fieldset className="filter-section location-section">
              <legend className="sr-only">Lokasi</legend>
              <div className="filter-section-heading" aria-hidden="true">
                <span>Lokasi</span>
                <small>{locationOptions.length} area</small>
              </div>
              <div className="filter-choice-grid location-choices">
                {locationOptions.map((location) => (
                  <label key={location.value} className="filter-choice">
                    <input
                      type="checkbox"
                      checked={draft.locations.includes(location.value)}
                      onChange={() =>
                        setDraft((current) => ({
                          ...current,
                          locations: toggleFilterValue(
                            current.locations,
                            location.value,
                          ),
                        }))
                      }
                    />
                    <span className="filter-check" aria-hidden="true" />
                    <span>{location.value}</span>
                  </label>
                ))}
                {locationOptions.length === 0 ? (
                  <p className="filter-options-empty">
                    Belum ada lokasi terindeks.
                  </p>
                ) : null}
              </div>
            </fieldset>
          </div>

          <div className="filter-panel-footer">
            <button
              type="button"
              className="filter-reset"
              disabled={draftActiveCount === 0}
              onClick={clearFilters}
            >
              Atur ulang
            </button>
            <button
              type="button"
              className="filter-apply"
              disabled={Boolean(priceError)}
              onClick={applyFilters}
            >
              Terapkan filter
            </button>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function ListingCard({
  listing,
  priority,
  onOpen,
}: {
  listing: Listing;
  priority?: boolean;
  onOpen: (listing: Listing) => void;
}) {
  const images = listing.images;
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
      }, 900);
    }, 280);
  }

  useEffect(
    () => () => {
      if (intentTimer.current) clearTimeout(intentTimer.current);
      if (carouselTimer.current) clearInterval(carouselTimer.current);
    },
    [],
  );

  const activeImageRecord = images[activeImage];

  return (
    <article
      className={`listing-card ${listing.status === "sold" ? "card-sold" : ""}`}
    >
      <button
        type="button"
        className="listing-image image-square"
        onClick={() => onOpen(listing)}
        onPointerEnter={startPreview}
        onPointerLeave={() => stopPreview()}
        onPointerCancel={() => stopPreview()}
      >
        <span className="carousel-media" aria-hidden="true">
          <span className="listing-image-placeholder">RECON</span>
          {activeImageRecord ? (
            <Image
              key={activeImageRecord.sourceUrl}
              className="carousel-frame is-active"
              src={activeImageRecord.sourceUrl}
              alt=""
              fill
              unoptimized
              priority={priority && activeImage === 0}
              referrerPolicy="no-referrer"
              onError={(event) => {
                event.currentTarget.style.display = "none";
              }}
              sizes="(max-width: 520px) 48vw, (max-width: 900px) 32vw, (max-width: 1280px) 25vw, 20vw"
            />
          ) : null}
        </span>
        {images.length > 1 ? (
          <span className="carousel-dots" aria-hidden="true">
            {images.map((image, index) => (
              <i
                key={`${image.sourceUrl}-${index}`}
                className={index === activeImage ? "active" : undefined}
              />
            ))}
          </span>
        ) : null}
        <span className="sr-only">{listing.title}</span>
      </button>

      <button
        type="button"
        className="listing-copy"
        onClick={() => onOpen(listing)}
      >
        <span className="listing-title">{listing.title}</span>
        <span className="listing-price">{formatRupiah(listing.price)}</span>
        <span className="listing-source">
          <VerifiedIcon />
          <span>{platformMeta[listing.platform].label}</span>
          <span className="listing-posted-at" suppressHydrationWarning>
            {formatListedAt(listing.listedAt)}
          </span>
        </span>
      </button>
    </article>
  );
}

function MasonryFeed({
  listings,
  onOpen,
}: {
  listings: Listing[];
  onOpen: (listing: Listing) => void;
}) {
  const [columnCount, setColumnCount] = useState(5);

  useEffect(() => {
    function updateColumnCount() {
      setColumnCount(getMasonryColumnCount(window.innerWidth));
    }

    updateColumnCount();
    window.addEventListener("resize", updateColumnCount);
    return () => window.removeEventListener("resize", updateColumnCount);
  }, []);

  const columns = useMemo(
    () =>
      distributeAcrossColumns(
        listings.map((listing, index) => ({ listing, index })),
        columnCount,
      ),
    [columnCount, listings],
  );
  const style = { "--masonry-columns": columnCount } as CSSProperties;

  return (
    <div className="masonry-feed" style={style}>
      {columns.map((column, columnIndex) => (
        <div className="masonry-column" key={columnIndex}>
          {column.map(({ listing, index }) => (
            <ListingCard
              key={listing.id}
              listing={listing}
              priority={index < columnCount}
              onOpen={onOpen}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

const descriptionPreviewLimit = 240;

function previewDescription(description: string) {
  if (description.length <= descriptionPreviewLimit) {
    return { text: description, isTruncated: false };
  }

  const clipped = description.slice(0, descriptionPreviewLimit + 1);
  const lastSpace = clipped.lastIndexOf(" ");
  return {
    text: clipped.slice(0, lastSpace > 0 ? lastSpace : descriptionPreviewLimit),
    isTruncated: true,
  };
}

function categoryLabel(category: string | null) {
  return category ?? "Tidak disebutkan";
}

function ListingDialog({
  listing,
  onClose,
}: {
  listing: Listing | null;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const pointerStartX = useRef<number | null>(null);
  const titleId = useId();
  const descriptionId = useId();
  const [carouselState, setCarouselState] = useState<{
    listingId: string | null;
    index: number;
  }>({ listingId: null, index: 0 });
  const description = listing
    ? previewDescription(listing.description)
    : { text: "", isTruncated: false };
  const images = listing?.images ?? [];
  const activeImage =
    carouselState.listingId === listing?.id
      ? Math.min(carouselState.index, images.length - 1)
      : 0;
  const hasMultipleImages = images.length > 1;
  const activeImageRecord = images[activeImage];

  function closeDialog() {
    pointerStartX.current = null;
    setCarouselState({ listingId: null, index: 0 });
    onClose();
  }

  function goToImage(index: number) {
    if (!listing) return;
    setCarouselState({
      listingId: listing.id,
      index: Math.min(images.length - 1, Math.max(0, index)),
    });
  }

  function moveImage(step: -1 | 1) {
    goToImage(stepCarouselIndex(activeImage, step, images.length));
  }

  function handleCarouselPointerDown(
    event: React.PointerEvent<HTMLDivElement>,
  ) {
    if (!hasMultipleImages || (event.target as HTMLElement).closest("button")) {
      return;
    }

    pointerStartX.current = event.clientX;
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handleCarouselPointerUp(event: React.PointerEvent<HTMLDivElement>) {
    const startX = pointerStartX.current;
    pointerStartX.current = null;
    if (startX === null) return;

    const distance = event.clientX - startX;
    if (Math.abs(distance) >= 48) moveImage(distance > 0 ? -1 : 1);
  }

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
      aria-labelledby={listing ? titleId : undefined}
      onClose={closeDialog}
      onClick={(event) => {
        if (event.target === event.currentTarget) closeDialog();
      }}
      onKeyDown={(event) => {
        if (!hasMultipleImages) return;
        if (event.key === "ArrowLeft") {
          event.preventDefault();
          moveImage(-1);
        } else if (event.key === "ArrowRight") {
          event.preventDefault();
          moveImage(1);
        }
      }}
    >
      {listing ? (
        <div className="dialog-card">
          <button
            type="button"
            className="dialog-close"
            onClick={closeDialog}
            aria-label="Tutup detail listing"
            data-autofocus
          >
            <CloseIcon />
          </button>
          <div
            className="dialog-image"
            role="region"
            aria-roledescription="carousel"
            aria-label={`Foto ${listing.title}`}
            onPointerDown={handleCarouselPointerDown}
            onPointerUp={handleCarouselPointerUp}
            onPointerCancel={() => {
              pointerStartX.current = null;
            }}
          >
            <div
              className="dialog-carousel-track"
              style={{ transform: "translate3d(0, 0, 0)" }}
            >
              <div className="dialog-carousel-slide dialog-image-placeholder">
                RECON
              </div>
              {activeImageRecord ? (
                <div className="dialog-carousel-slide">
                  <Image
                    key={activeImageRecord.sourceUrl}
                    src={activeImageRecord.sourceUrl}
                    alt={`${activeImageRecord.altText ?? listing.title}${images.length > 1 ? `, foto ${activeImage + 1} dari ${images.length}` : ""}`}
                    fill
                    draggable={false}
                    priority={activeImage === 0}
                    unoptimized
                    referrerPolicy="no-referrer"
                    onError={(event) => {
                      event.currentTarget.style.display = "none";
                    }}
                    sizes="(max-width: 760px) 100vw, 54vw"
                  />
                </div>
              ) : null}
            </div>

            {hasMultipleImages ? (
              <>
                <button
                  type="button"
                  className="dialog-carousel-arrow is-previous"
                  onClick={() => moveImage(-1)}
                  disabled={activeImage === 0}
                  aria-label="Foto sebelumnya"
                >
                  <CarouselArrowIcon direction="left" />
                </button>
                <button
                  type="button"
                  className="dialog-carousel-arrow is-next"
                  onClick={() => moveImage(1)}
                  disabled={activeImage === images.length - 1}
                  aria-label="Foto berikutnya"
                >
                  <CarouselArrowIcon direction="right" />
                </button>

                <span className="dialog-carousel-count" aria-hidden="true">
                  {activeImage + 1} / {images.length}
                </span>
                <div className="dialog-carousel-dots" aria-label="Pilih foto">
                  {images.map((image, index) => (
                    <button
                      key={`${image.sourceUrl}-dot-${index}`}
                      type="button"
                      className={
                        index === activeImage ? "is-active" : undefined
                      }
                      onClick={() => goToImage(index)}
                      aria-label={`Tampilkan foto ${index + 1}`}
                      aria-current={index === activeImage ? "true" : undefined}
                    />
                  ))}
                </div>
                <span className="sr-only" aria-live="polite">
                  Foto {activeImage + 1} dari {images.length}
                </span>
              </>
            ) : null}
          </div>
          <div className="dialog-copy">
            <div className="dialog-source-meta">
              <VerifiedIcon />
              <span>{platformMeta[listing.platform].label}</span>
              <span aria-hidden="true">·</span>
              <span suppressHydrationWarning>
                {formatListedAt(listing.listedAt)}
              </span>
            </div>
            <h2 id={titleId}>{listing.title}</h2>
            <p className="dialog-price">{formatRupiah(listing.price)}</p>
            <section
              className="dialog-description"
              aria-labelledby={descriptionId}
            >
              <h3 id={descriptionId}>Deskripsi</h3>
              <p>
                {description.text}
                {description.isTruncated ? (
                  <>
                    …{" "}
                    <a
                      href={listing.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Lihat selengkapnya
                    </a>
                  </>
                ) : null}
              </p>
            </section>
            <dl className="dialog-facts">
              <div>
                <dt>Kategori</dt>
                <dd>{categoryLabel(listing.category)}</dd>
              </div>
              <div>
                <dt>Merek</dt>
                <dd>{listing.brand ?? "Tidak disebutkan"}</dd>
              </div>
              <div>
                <dt>Kondisi</dt>
                <dd>{listing.conditionText ?? "Tidak disebutkan"}</dd>
              </div>
              <div>
                <dt>Lokasi</dt>
                <dd>
                  {listing.locationTexts.length > 0
                    ? listing.locationTexts.join(", ")
                    : "Tidak disebutkan"}
                </dd>
              </div>
              <div>
                <dt>Penjual</dt>
                <dd>{listing.sellerName ?? "Tidak disebutkan"}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>{statusMeta[listing.status].label}</dd>
              </div>
            </dl>
            <div className="dialog-actions">
              <a
                className="primary-action"
                href={listing.sourceUrl}
                target="_blank"
                rel="noreferrer"
              >
                Buka postingan di {platformMeta[listing.platform].label}
                <ArrowIcon />
              </a>
            </div>
          </div>
        </div>
      ) : null}
    </dialog>
  );
}

export function ReconFeed({ scope }: ReconFeedProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const utils = api.useUtils();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [hasNewListings, setHasNewListings] = useState(false);
  const [refreshAnnouncement, setRefreshAnnouncement] = useState("");
  const [selectedListing, setSelectedListing] = useState<Listing | null>(null);
  const query = (searchParams.get("q") ?? "").trim().slice(0, 80);
  const parsedFilters = useMemo(
    () => parseListingFilters(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );
  const filters = useMemo<ListingFilters>(
    () =>
      scope.type === "platform"
        ? { ...parsedFilters, platforms: [scope.slug] }
        : parsedFilters,
    [parsedFilters, scope],
  );
  const feedInput = useMemo(
    () => buildListingFeedInput(scope, filters, query),
    [filters, query, scope],
  );
  const feedQuery = api.listings.feed.useInfiniteQuery(feedInput, {
    ...manualListingRefreshQueryOptions,
    initialCursor: undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
  });
  const facetsQuery = api.listings.facets.useQuery(
    undefined,
    manualListingRefreshQueryOptions,
  );
  const versionQuery = api.listings.version.useQuery(undefined, {
    refetchInterval: 30 * 1000,
    refetchIntervalInBackground: false,
    refetchOnReconnect: true,
    refetchOnWindowFocus: true,
    retry: 1,
    staleTime: 0,
  });
  const seenListingRevision = useRef(versionQuery.data?.revision ?? null);

  useEffect(() => {
    const currentRevision = versionQuery.data?.revision ?? null;
    if (!currentRevision) return;

    if (!seenListingRevision.current) {
      seenListingRevision.current = currentRevision;
      return;
    }

    if (
      hasUnseenListingRevision(
        seenListingRevision.current,
        currentRevision,
      )
    ) {
      setHasNewListings(true);
      setRefreshAnnouncement(
        "Temuan baru tersedia. Gunakan tombol di bagian atas untuk memuatnya.",
      );
    }
  }, [versionQuery.data?.revision]);
  const listings = useMemo(() => {
    const uniqueListings = new Map<string, Listing>();
    for (const page of feedQuery.data?.pages ?? []) {
      for (const listing of page.items) uniqueListings.set(listing.id, listing);
    }
    return Array.from(uniqueListings.values());
  }, [feedQuery.data]);
  const locationOptions = useMemo(
    () =>
      mergeSelectedFacetOptions(
        facetsQuery.data?.locations ?? [],
        filters.locations,
      ),
    [facetsQuery.data?.locations, filters.locations],
  );
  const conditionOptions = useMemo(
    () =>
      mergeSelectedFacetOptions(
        facetsQuery.data?.conditions ?? [],
        filters.conditions,
      ),
    [facetsQuery.data?.conditions, filters.conditions],
  );

  const baseParams = new URLSearchParams(searchParams.toString());

  function collectionHref(slug: string) {
    const next = new URLSearchParams(baseParams.toString());
    if (scope.type === "platform") {
      next.delete("platform");
      next.append("platform", scope.slug);
    }

    return withQuery(`/collection/${slug}`, next);
  }

  function changeFilters(nextFilters: ListingFilters) {
    const next = setListingFilterParams(
      new URLSearchParams(searchParams.toString()),
      nextFilters,
    );
    const targetPath = scope.type === "platform" ? "/collection/all" : pathname;

    router.push(withQuery(targetPath, next), { scroll: false });
  }

  async function refreshFeed() {
    if (isRefreshing) return;

    setIsRefreshing(true);
    setRefreshAnnouncement("Memperbarui listing…");

    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    window.scrollTo({
      top: 0,
      behavior: prefersReducedMotion ? "auto" : "smooth",
    });

    try {
      const revisionResult = await versionQuery.refetch();
      await Promise.all([
        utils.listings.feed.reset(feedInput, { throwOnError: true }),
        utils.listings.facets.reset(undefined, { throwOnError: true }),
      ]);
      if (revisionResult.data?.revision) {
        seenListingRevision.current = revisionResult.data.revision;
      }
      setHasNewListings(false);
      setRefreshAnnouncement("Temuan terbaru sudah dimuat.");
    } catch {
      setRefreshAnnouncement("Temuan belum berhasil diperbarui. Coba lagi.");
    } finally {
      setIsRefreshing(false);
    }
  }

  return (
    <div className="app-shell">
      <ReconHeader
        refreshControl={{
          hasNewListings,
          isRefreshing,
          onRefresh: () => void refreshFeed(),
        }}
      >
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

          <div className="feed-controls">
            <FilterControl
              filters={filters}
              locationOptions={locationOptions}
              conditionOptions={conditionOptions}
              onApply={changeFilters}
              onClear={() => changeFilters(emptyListingFilters)}
            />
            <span className="feed-order-label" aria-label="Urutan terbaru">
              Terbaru
            </span>
          </div>
        </div>
      </ReconHeader>

      <main className="feed-main">
        <h1 className="sr-only">{titleForScope(scope)}</h1>
        <p className="sr-only" aria-live="polite">
          {listings.length} listing sudah dimuat
        </p>
        <p className="sr-only" aria-live="polite">
          {refreshAnnouncement}
        </p>

        <div
          className="feed-refresh-stage"
          data-refreshing={isRefreshing || feedQuery.isPending}
          aria-busy={isRefreshing || feedQuery.isPending}
        >
          <div className="feed-refresh-indicator" aria-hidden={!isRefreshing}>
            <FeedRefreshSpinner />
          </div>
          <div className="feed-refresh-content">
            {query ? (
              <div className="query-banner">
                <p>
                  Hasil pencarian untuk <strong>“{query}”</strong>
                </p>
                <Link
                  href={withQuery(
                    scope.type === "platform"
                      ? `/platform/${scope.slug}`
                      : `/collection/${scope.slug}`,
                    clearKey(baseParams, "q"),
                  )}
                >
                  Hapus pencarian
                </Link>
              </div>
            ) : null}

            {feedQuery.isPending ? (
              <FeedSkeleton />
            ) : feedQuery.isError ? (
              <section className="empty-state feed-error-state" role="alert">
                <h2>Temuan belum berhasil dimuat.</h2>
                <p>
                  Koneksi ke data RECON sedang bermasalah. Coba sekali lagi.
                </p>
                <button type="button" onClick={() => void feedQuery.refetch()}>
                  Coba lagi
                </button>
              </section>
            ) : listings.length > 0 ? (
              <MasonryFeed listings={listings} onOpen={setSelectedListing} />
            ) : (
              <section className="empty-state">
                <h2>Belum ada listing yang cocok.</h2>
                <p>Coba longgarkan filter atau hapus pencarian.</p>
                <Link href="/collection/all">Kembali ke semua listing</Link>
              </section>
            )}

            {feedQuery.hasNextPage ? (
              <div className="load-more-wrap">
                <button
                  type="button"
                  disabled={feedQuery.isFetchingNextPage}
                  onClick={() => void feedQuery.fetchNextPage()}
                >
                  {feedQuery.isFetchingNextPage
                    ? "Memuat temuan…"
                    : "Muat temuan berikutnya"}
                  <span>12 temuan per muat</span>
                </button>
              </div>
            ) : listings.length > 0 && !feedQuery.isError ? (
              <p className="feed-end">Semua listing sudah ditampilkan.</p>
            ) : null}
          </div>
        </div>

        <footer className="feed-footer">
          <p>RECON</p>
          <p>Temuan publik dari sumber aslinya.</p>
        </footer>
      </main>

      <ListingDialog
        listing={selectedListing}
        onClose={() => setSelectedListing(null)}
      />
    </div>
  );
}

function mergeSelectedFacetOptions(
  options: readonly { value: string; count: number }[],
  selected: readonly string[],
) {
  const merged = new Map(options.map((option) => [option.value, option]));
  for (const value of selected) {
    if (!merged.has(value)) merged.set(value, { value, count: 0 });
  }
  return Array.from(merged.values());
}

function FeedSkeleton() {
  return (
    <div className="feed-skeleton" aria-label="Memuat temuan">
      {Array.from({ length: 10 }, (_, index) => (
        <div className="feed-skeleton-card" key={index} aria-hidden="true">
          <span />
          <i />
          <i />
        </div>
      ))}
    </div>
  );
}
