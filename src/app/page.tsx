export default async function Home() {
  return (
    <main className="flex min-h-screen flex-col bg-neutral-950 text-neutral-100">
      <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col justify-center px-6 py-16">
        <p className="mb-3 text-sm font-medium uppercase tracking-wide text-neutral-400">
          Recon phase 1
        </p>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-normal text-white sm:text-5xl">
          Database foundation for monitored preloved tech listings.
        </h1>
        <p className="mt-5 max-w-2xl text-base leading-7 text-neutral-300">
          The public app surface is intentionally quiet while scraper,
          normalization, and storage contracts are being hardened.
        </p>
      </div>
    </main>
  );
}
