import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { ReconHeader } from "~/components/recon-header";

export const metadata: Metadata = {
  title: "Cara kerja & batasan",
  description:
    "Pelajari bagaimana RECON menyusun temuan listing dan apa yang tetap perlu kamu periksa sendiri.",
  alternates: { canonical: "/cara-kerja" },
  openGraph: { url: "/cara-kerja" },
};

const steps = [
  {
    number: "01",
    title: "Menemukan",
    description:
      "RECON mengambil informasi listing dari sumber pihak ketiga yang dapat diakses saat proses berjalan.",
  },
  {
    number: "02",
    title: "Merapikan",
    description:
      "Pemrosesan otomatis membantu membaca kategori, harga, kondisi, lokasi umum, dan status dari informasi sumber.",
  },
  {
    number: "03",
    title: "Menyusun",
    description:
      "Hasil yang relevan disusun menjadi satu feed dan ditautkan kembali ke posting asal.",
  },
  {
    number: "04",
    title: "Kamu memeriksa",
    description:
      "Sebelum bertransaksi, buka sumber asal dan periksa kembali penjual, barang, harga, serta ketersediaannya.",
  },
] as const;

const limitations = [
  {
    label: "Penjual",
    text: "RECON tidak memverifikasi identitas, reputasi, atau kewenangan penjual.",
  },
  {
    label: "Barang",
    text: "RECON tidak memeriksa kepemilikan, keaslian, kondisi, kelengkapan, atau garansi barang.",
  },
  {
    label: "Informasi",
    text: "Harga, lokasi, deskripsi, dan status dapat tidak lengkap, keliru, atau sudah berubah.",
  },
  {
    label: "Transaksi",
    text: "RECON tidak menerima pembayaran, mengatur pengiriman, atau menjadi pihak dalam transaksi.",
  },
] as const;

export default function HowItWorksPage() {
  return (
    <div className="app-shell">
      <Suspense fallback={<div className="header-placeholder" />}>
        <ReconHeader />
      </Suspense>

      <main className="trust-page">
        <section className="trust-hero">
          <p className="eyebrow">Cara kerja / batasan</p>
          <h1>Satu feed untuk mencari. Sumber asal untuk memastikan.</h1>
          <div className="trust-hero-note">
            <span>Bukan marketplace</span>
            <p>
              RECON adalah layanan discovery independen. Kami membantu merapikan
              pencarian, bukan menjamin transaksi.
            </p>
          </div>
        </section>

        <section className="process-section" aria-labelledby="process-title">
          <div className="section-heading">
            <p className="eyebrow">Alur temuan</p>
            <h2 id="process-title">Dari sumber ke feed.</h2>
          </div>
          <ol className="process-grid">
            {steps.map((step) => (
              <li key={step.number}>
                <span>{step.number}</span>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="limits-section" aria-labelledby="limits-title">
          <div className="limits-intro">
            <p className="eyebrow">Yang tidak kami janjikan</p>
            <h2 id="limits-title">Temuan bukan verifikasi.</h2>
            <p>
              Pemrosesan otomatis bisa salah. Keterangan pada sumber juga bisa
              berubah setelah terakhir ditemukan RECON.
            </p>
          </div>
          <dl className="limits-list">
            {limitations.map((item) => (
              <div key={item.label}>
                <dt>{item.label}</dt>
                <dd>{item.text}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="timestamp-note" aria-labelledby="time-title">
          <div>
            <p className="eyebrow">Tentang waktu</p>
            <h2 id="time-title">
              “Ditemukan” tidak selalu berarti “diposting”.
            </h2>
          </div>
          <p>
            Jika tanggal posting tersedia, RECON dapat menampilkannya. Jika
            tidak, waktu yang terlihat dapat merujuk pada saat listing pertama
            kali ditemukan RECON. Karena itu, selalu lihat sumber asal untuk
            status terbaru.
          </p>
        </section>

        <section className="trust-cta">
          <p>
            Menemukan informasi yang tidak tepat atau punya pertanyaan tentang
            cara RECON bekerja?
          </p>
          <a href="mailto:recon@app-pixel.com">Hubungi recon@app-pixel.com</a>
          <Link href="/privacy">Baca kebijakan privasi</Link>
        </section>
      </main>
    </div>
  );
}
