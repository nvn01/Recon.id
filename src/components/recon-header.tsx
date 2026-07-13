"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m21 21-4.35-4.35m2.35-5.4a7.75 7.75 0 1 1-15.5 0 7.75 7.75 0 0 1 15.5 0Z" />
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

export function ReconHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const query = searchParams.get("q") ?? "";

  function submitSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const value = String(data.get("q") ?? "").trim();
    const next = new URLSearchParams(searchParams.toString());

    if (value) next.set("q", value);
    else next.delete("q");

    const suffix = next.toString();
    const targetPath = pathname === "/platform" ? "/collection/all" : pathname;
    router.push(`${targetPath}${suffix ? `?${suffix}` : ""}`);
  }

  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="wordmark" href="/collection/all" aria-label="RECON home">
          <ReconMark />
          <span>RECON</span>
        </Link>

        <nav className="primary-nav" aria-label="Navigasi utama">
          <Link href="/collection/all">Jelajah</Link>
          <Link href="/platform">Platform</Link>
        </nav>

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
          <kbd>Enter</kbd>
        </form>

        <div className="header-status" aria-label="Status pemantauan">
          <span className="live-dot" />
          <span>SCAN AKTIF</span>
        </div>
      </div>
    </header>
  );
}
