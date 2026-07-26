import { Suspense, type ReactNode } from "react";

import { ReconHeader } from "~/components/recon-header";

type EditorialPageProps = {
  title: string;
  introduction: string;
  updated?: string;
  children: ReactNode;
};

export function EditorialPage({
  title,
  introduction,
  updated,
  children,
}: EditorialPageProps) {
  return (
    <div className="app-shell">
      <Suspense fallback={<div className="header-placeholder" />}>
        <ReconHeader />
      </Suspense>

      <main className="editorial-page" lang="en">
        <header className="editorial-page-hero">
          <h1>{title}</h1>
          <div>
            <p>{introduction}</p>
            {updated ? <span>Last updated {updated}</span> : null}
          </div>
        </header>
        <article className="editorial-page-copy">{children}</article>
      </main>
    </div>
  );
}
