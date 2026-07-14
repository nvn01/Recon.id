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
  collections,
  dummyListings,
  formatRupiah,
  platformMeta,
  type DummyListing,
  type ListingPlatform,
  type ListingStatus,
} from "~/data/dummy-listings";
import {
  countActiveFilterGroups,
  emptyListingFilters,
  filterListings,
  listingConditions,
  listingLocations,
  parseListingFilters,
  setListingFilterParams,
  type ListingFilters,
} from "~/data/listing-filter";
import {
  defaultListingSort,
  listingSortOptions,
  parseListingSort,
  sortListings,
  type ListingSort,
} from "~/data/listing-sort";
import {
  distributeAcrossColumns,
  getMasonryColumnCount,
} from "~/data/masonry-layout";

type FeedScope =
  | { type: "collection"; slug: string }
  | { type: "platform"; slug: ListingPlatform };

type ReconFeedProps = {
  scope: FeedScope;
};

const statusMeta: Record<ListingStatus, { label: string }> = {
  available: { label: "Tersedia" },
  unknown: { label: "Perlu cek" },
  sold: { label: "Terjual" },
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

function SortIcon() {
  return (
    <span className="sort-icon" aria-hidden="true">
      <i />
      <i />
      <i />
    </span>
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

function selectListingsForFeed(
  listings: readonly DummyListing[],
  filters: ListingFilters,
  scope: FeedScope,
  query: string,
  sort: ListingSort,
) {
  const filtered = filterListings(listings, filters).filter((listing) => {
    const categoryMatches =
      scope.type !== "collection" ||
      scope.slug === "all" ||
      listing.category === scope.slug;
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

    return categoryMatches && queryMatches;
  });

  return sortListings(filtered, sort);
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
  onApply,
  onClear,
}: {
  filters: ListingFilters;
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
                {listingConditions.map((condition) => (
                  <label key={condition} className="filter-choice">
                    <input
                      type="checkbox"
                      checked={draft.conditions.includes(condition)}
                      onChange={() =>
                        setDraft((current) => ({
                          ...current,
                          conditions: toggleFilterValue(
                            current.conditions,
                            condition,
                          ),
                        }))
                      }
                    />
                    <span className="filter-check" aria-hidden="true" />
                    <span>{conditionLabel(condition)}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <fieldset className="filter-section location-section">
              <legend className="sr-only">Lokasi</legend>
              <div className="filter-section-heading" aria-hidden="true">
                <span>Lokasi</span>
                <small>{listingLocations.length} area</small>
              </div>
              <div className="filter-choice-grid location-choices">
                {listingLocations.map((location) => (
                  <label key={location} className="filter-choice">
                    <input
                      type="checkbox"
                      checked={draft.locations.includes(location)}
                      onChange={() =>
                        setDraft((current) => ({
                          ...current,
                          locations: toggleFilterValue(
                            current.locations,
                            location,
                          ),
                        }))
                      }
                    />
                    <span className="filter-check" aria-hidden="true" />
                    <span>{location}</span>
                  </label>
                ))}
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

function SortControl({
  sort,
  onChange,
}: {
  sort: ListingSort;
  onChange: (value: ListingSort) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const menuId = useId();
  const matchedIndex = listingSortOptions.findIndex(
    (option) => option.value === sort,
  );
  const selectedIndex = matchedIndex === -1 ? 0 : matchedIndex;
  const selectedOption =
    listingSortOptions[selectedIndex] ?? listingSortOptions[0];

  useEffect(() => {
    if (!isOpen) return;

    function handleOutsidePointer(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setIsOpen(false);
    }

    document.addEventListener("pointerdown", handleOutsidePointer);
    return () =>
      document.removeEventListener("pointerdown", handleOutsidePointer);
  }, [isOpen]);

  function focusOption(index: number) {
    requestAnimationFrame(() => optionRefs.current[index]?.focus());
  }

  function handleTriggerKeyDown(event: React.KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setIsOpen(true);
      focusOption(selectedIndex);
    } else if (event.key === "Escape") {
      setIsOpen(false);
    }
  }

  function handleOptionKeyDown(
    event: React.KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) {
    if (event.key === "Escape") {
      event.preventDefault();
      setIsOpen(false);
      triggerRef.current?.focus();
      return;
    }

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      const option = listingSortOptions[index];
      if (option) chooseSort(option.value);
      return;
    }

    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;

    event.preventDefault();
    const lastIndex = listingSortOptions.length - 1;
    const nextIndex =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? lastIndex
          : event.key === "ArrowDown"
            ? (index + 1) % listingSortOptions.length
            : (index - 1 + listingSortOptions.length) %
              listingSortOptions.length;
    optionRefs.current[nextIndex]?.focus();
  }

  function chooseSort(value: ListingSort) {
    onChange(value);
    setIsOpen(false);
    requestAnimationFrame(() => triggerRef.current?.focus());
  }

  return (
    <div
      ref={rootRef}
      className="sort-control"
      data-open={isOpen ? "true" : "false"}
    >
      <button
        ref={triggerRef}
        type="button"
        className="sort-trigger"
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-controls={menuId}
        aria-label={`Urutkan listing, saat ini ${selectedOption.label}`}
        onClick={() => setIsOpen((open) => !open)}
        onKeyDown={handleTriggerKeyDown}
      >
        <SortIcon />
        <span className="sort-current">{selectedOption.label}</span>
        <span className="sort-chevron" aria-hidden="true" />
      </button>

      {isOpen ? (
        <div id={menuId} className="sort-menu" role="menu">
          {listingSortOptions.map((option, index) => (
            <button
              key={option.value}
              ref={(element) => {
                optionRefs.current[index] = element;
              }}
              type="button"
              role="menuitemradio"
              aria-checked={option.value === sort}
              className={option.value === sort ? "is-selected" : undefined}
              onClick={() => chooseSort(option.value)}
              onKeyDown={(event) => handleOptionKeyDown(event, index)}
            >
              {option.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
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

  return (
    <article
      className={`listing-card ${listing.status === "sold" ? "card-sold" : ""}`}
    >
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
              unoptimized={!imageUrl.startsWith("https://images.unsplash.com/")}
              priority={priority && index === 0}
              sizes="(max-width: 520px) 48vw, (max-width: 900px) 32vw, (max-width: 1280px) 25vw, 20vw"
            />
          ))}
        </span>
        {images.length > 1 ? (
          <span className="carousel-dots" aria-hidden="true">
            {images.map((imageUrl, index) => (
              <i
                key={imageUrl}
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
          <span className="listing-posted-at">{listing.postedLabel}</span>
        </span>
      </button>
    </article>
  );
}

function MasonryFeed({
  listings,
  onOpen,
}: {
  listings: DummyListing[];
  onOpen: (listing: DummyListing) => void;
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

function categoryLabel(category: string) {
  return (
    collections.find((collection) => collection.slug === category)?.label ??
    category
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
  const images = listing
    ? [listing.imageUrl, ...(listing.previewImageUrls ?? [])]
    : [];
  const activeImage =
    carouselState.listingId === listing?.id
      ? Math.min(carouselState.index, images.length - 1)
      : 0;
  const hasMultipleImages = images.length > 1;

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
              style={{
                transform: `translate3d(-${activeImage * 100}%, 0, 0)`,
              }}
            >
              {images.map((imageUrl, index) => (
                <div
                  key={`${imageUrl}-${index}`}
                  className="dialog-carousel-slide"
                  aria-hidden={index !== activeImage}
                >
                  <Image
                    src={imageUrl}
                    alt={
                      index === activeImage
                        ? `${listing.imageAlt}${images.length > 1 ? `, foto ${index + 1} dari ${images.length}` : ""}`
                        : ""
                    }
                    fill
                    draggable={false}
                    priority={index === 0}
                    unoptimized={
                      !imageUrl.startsWith("https://images.unsplash.com/")
                    }
                    sizes="(max-width: 760px) 100vw, 54vw"
                  />
                </div>
              ))}
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
                  {images.map((imageUrl, index) => (
                    <button
                      key={`${imageUrl}-dot-${index}`}
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
              <span>{listing.postedLabel}</span>
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
                <dd>{listing.brand}</dd>
              </div>
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
  const [visibleCount, setVisibleCount] = useState(12);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshAnnouncement, setRefreshAnnouncement] = useState("");
  const [selectedListing, setSelectedListing] = useState<DummyListing | null>(
    null,
  );
  const query = (searchParams.get("q") ?? "").trim().toLowerCase();
  const sort = parseListingSort(searchParams.get("sort"));
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

  const filteredListings = useMemo(
    () => selectListingsForFeed(dummyListings, filters, scope, query, sort),
    [filters, query, scope, sort],
  );

  const baseParams = new URLSearchParams(searchParams.toString());
  baseParams.delete("status");

  function collectionHref(slug: string) {
    const next = new URLSearchParams(baseParams.toString());
    if (scope.type === "platform") {
      next.delete("platform");
      next.append("platform", scope.slug);
    }

    return withQuery(`/collection/${slug}`, next);
  }

  function changeSort(value: ListingSort) {
    const next = new URLSearchParams(searchParams.toString());

    if (value === defaultListingSort) next.delete("sort");
    else next.set("sort", value);

    setVisibleCount(12);
    router.push(withQuery(pathname, next), { scroll: false });
  }

  function changeFilters(nextFilters: ListingFilters) {
    const next = setListingFilterParams(
      new URLSearchParams(searchParams.toString()),
      nextFilters,
    );
    const targetPath = scope.type === "platform" ? "/collection/all" : pathname;

    setVisibleCount(12);
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
      await new Promise<void>((resolve) => window.setTimeout(resolve, 800));
      setVisibleCount(12);
      setRefreshAnnouncement("Tampilan contoh sudah diperbarui.");
    } finally {
      setIsRefreshing(false);
    }
  }

  const shownListings = filteredListings.slice(0, visibleCount);

  return (
    <div className="app-shell">
      <ReconHeader
        refreshControl={{
          newCount: 0,
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
              onApply={changeFilters}
              onClear={() => changeFilters(emptyListingFilters)}
            />
            <SortControl sort={sort} onChange={changeSort} />
          </div>
        </div>
      </ReconHeader>

      <main className="feed-main">
        <h1 className="sr-only">{titleForScope(scope)}</h1>
        <p className="sr-only" aria-live="polite">
          {filteredListings.length} listing cocok
        </p>
        <p className="sr-only" aria-live="polite">
          {refreshAnnouncement}
        </p>

        <div
          className="feed-refresh-stage"
          data-refreshing={isRefreshing}
          aria-busy={isRefreshing}
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

            {shownListings.length > 0 ? (
              <MasonryFeed
                listings={shownListings}
                onOpen={setSelectedListing}
              />
            ) : (
              <section className="empty-state">
                <h2>Belum ada listing yang cocok.</h2>
                <p>Coba longgarkan filter atau hapus pencarian.</p>
                <Link href="/collection/all">Kembali ke semua listing</Link>
              </section>
            )}

            {visibleCount < filteredListings.length ? (
              <div className="load-more-wrap">
                <button
                  type="button"
                  onClick={() => setVisibleCount((count) => count + 6)}
                >
                  Muat temuan berikutnya
                  <span>{filteredListings.length - visibleCount} tersisa</span>
                </button>
              </div>
            ) : shownListings.length > 0 ? (
              <p className="feed-end">Semua listing sudah ditampilkan.</p>
            ) : null}
          </div>
        </div>

        <footer className="feed-footer">
          <p>RECON</p>
          <p>Listing contoh dengan foto dari Unsplash.</p>
        </footer>
      </main>

      <ListingDialog
        listing={selectedListing}
        onClose={() => setSelectedListing(null)}
      />
    </div>
  );
}
