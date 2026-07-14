"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type ReactNode } from "react";

import { RefreshArrowIcon } from "~/components/refresh-arrow-icon";

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m21 21-4.35-4.35m2.35-5.4a7.75 7.75 0 1 1-15.5 0 7.75 7.75 0 0 1 15.5 0Z" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m7 7 10 10M17 7 7 17" />
    </svg>
  );
}

export function ReconMark() {
  return (
    <span className="recon-mark" aria-hidden="true">
      <span />
      <span />
    </span>
  );
}

export type FeedRefreshControl = {
  newCount: number;
  isRefreshing: boolean;
  onRefresh: () => void;
};

export function ReconHeader({
  children,
  refreshControl,
}: {
  children?: ReactNode;
  refreshControl?: FeedRefreshControl;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const query = searchParams.get("q") ?? "";

  function searchPath() {
    return pathname === "/platform" || pathname === "/collection"
      ? "/collection/all"
      : pathname;
  }

  function submitSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const searchValue = data.get("q");
    const value = typeof searchValue === "string" ? searchValue.trim() : "";
    const next = new URLSearchParams(searchParams.toString());

    if (value) next.set("q", value);
    else next.delete("q");

    const suffix = next.toString();
    const targetPath = searchPath();
    router.push(`${targetPath}${suffix ? `?${suffix}` : ""}`);
  }

  function clearSearch() {
    const next = new URLSearchParams(searchParams.toString());
    next.delete("q");
    const targetPath = searchPath();
    router.push(`${targetPath}${next.size ? `?${next.toString()}` : ""}`);
  }

  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="wordmark" href="/collection" aria-label="RECON home">
          <ReconMark />
          <span>RECON</span>
        </Link>

        <form className="search-box" role="search" onSubmit={submitSearch}>
          <label className="sr-only" htmlFor="recon-search">
            Cari listing
          </label>
          <SearchIcon />
          <input
            key={query}
            id="recon-search"
            name="q"
            type="search"
            defaultValue={query}
            placeholder="Cari GPU, laptop, keyboard…"
            autoComplete="off"
          />
          {query ? (
            <button
              type="button"
              className="clear-search"
              onClick={clearSearch}
            >
              <CloseIcon />
              <span className="sr-only">Hapus pencarian</span>
            </button>
          ) : (
            <span className="search-hint">Cari</span>
          )}
        </form>

        <div className="header-actions">
          {refreshControl ? (
            <button
              type="button"
              className="feed-refresh-button"
              data-state={
                refreshControl.isRefreshing
                  ? "loading"
                  : refreshControl.newCount > 0
                    ? "new"
                    : "idle"
              }
              onClick={refreshControl.onRefresh}
              disabled={refreshControl.isRefreshing}
              aria-label={
                refreshControl.isRefreshing
                  ? "Memperbarui listing"
                  : refreshControl.newCount > 0
                    ? `Tampilkan ${refreshControl.newCount} listing baru`
                    : "Periksa listing baru"
              }
            >
              {refreshControl.isRefreshing ? (
                <RefreshArrowIcon />
              ) : (
                <span className="live-dot" />
              )}
              {refreshControl.newCount > 0 && !refreshControl.isRefreshing ? (
                <span className="feed-refresh-label">
                  {refreshControl.newCount} listing baru
                </span>
              ) : null}
            </button>
          ) : (
            <span className="header-presence" aria-label="Pemantauan aktif">
              <span className="live-dot" />
            </span>
          )}
        </div>
      </div>
      {children ? <div className="header-subnav">{children}</div> : null}
    </header>
  );
}
