import type { Metadata } from "next";
import Link from "next/link";

import { AnalyticsConsent } from "~/components/analytics-consent";

export const metadata: Metadata = {
  title: "Pilihan statistik",
  description: "Atur penggunaan statistik tambahan di RECON.",
  robots: {
    index: false,
    follow: true,
  },
  alternates: {
    canonical: "/privacy",
  },
};

export default function AnalyticsPreferencesPage() {
  return (
    <main className="trust-page">
      <div className="trust-page-inner">
        <p className="eyebrow">Pilihan privasi</p>
        <h1>Atur statistik RECON</h1>
        <p className="trust-page-lead">
          Pilih apakah RECON boleh memakai statistik tambahan yang sudah
          dibatasi agar tidak mengirim kata pencarian, identitas penjual,
          deskripsi listing, lokasi persis, atau URL sumber.
        </p>
        <p>
          Statistik dasar Cloudflare tetap digunakan untuk keamanan dan
          performa. Baca penjelasan lengkapnya di{" "}
          <Link href="/privacy">Kebijakan Privasi</Link>.
        </p>
      </div>
      <AnalyticsConsent forceOpen />
    </main>
  );
}
