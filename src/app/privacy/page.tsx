import type { Metadata } from "next";
import { Suspense } from "react";

import { ReconHeader } from "~/components/recon-header";

export const metadata: Metadata = {
  title: "Privasi",
  description:
    "Penjelasan mengenai data yang diproses RECON, tujuannya, serta cara mengajukan permintaan privasi.",
};

export default function PrivacyPage() {
  return (
    <div className="app-shell">
      <Suspense fallback={<div className="header-placeholder" />}>
        <ReconHeader />
      </Suspense>

      <main className="privacy-page">
        <header className="privacy-hero">
          <div>
            <p className="eyebrow">Privasi / RECON</p>
            <h1>Data secukupnya, dijelaskan apa adanya.</h1>
          </div>
          <div className="privacy-edition">
            <span>Berlaku</span>
            <strong>26 Juli 2026</strong>
            <p>
              Kebijakan ini menjelaskan praktik RECON saat ini. Kami akan
              memperbaruinya ketika praktik atau layanan berubah.
            </p>
          </div>
        </header>

        <div className="privacy-layout">
          <aside className="privacy-summary">
            <p className="eyebrow">Ringkasnya</p>
            <p>
              RECON memproses informasi listing untuk membuat feed pencarian.
              Kami belum menggunakan Google Analytics dan tidak menjual data
              pribadi.
            </p>
            <a href="mailto:recon@app-pixel.com">recon@app-pixel.com</a>
          </aside>

          <article className="privacy-copy">
            <section>
              <span>01</span>
              <div>
                <h2>Siapa yang mengelola RECON</h2>
                <p>
                  RECON adalah layanan discovery independen yang mengelola situs
                  dan feed ini. Untuk pertanyaan, koreksi, atau permintaan
                  privasi, hubungi{" "}
                  <a href="mailto:recon@app-pixel.com">recon@app-pixel.com</a>.
                </p>
              </div>
            </section>

            <section>
              <span>02</span>
              <div>
                <h2>Informasi listing yang diproses</h2>
                <p>
                  Bergantung pada sumber, RECON dapat memproses judul,
                  deskripsi, harga, kategori, merek, kondisi, status, lokasi
                  umum, nama tampilan penjual, tanggal posting atau ditemukan,
                  tautan sumber, pengenal posting, serta gambar dan informasi
                  pendampingnya.
                </p>
                <p>
                  Informasi tersebut berasal dari layanan pihak ketiga.
                  Ketersediaannya pada suatu sumber tidak berarti informasi itu
                  bebas dari hak privasi, hak cipta, atau ketentuan platform.
                </p>
              </div>
            </section>

            <section>
              <span>03</span>
              <div>
                <h2>Pemrosesan otomatis</h2>
                <p>
                  RECON menggunakan pemrosesan otomatis untuk menilai apakah
                  suatu posting merupakan listing dan untuk merapikan informasi
                  seperti judul, harga, kategori, kondisi, lokasi umum, dan
                  status. Hasilnya dapat keliru.
                </p>
                <p>
                  Untuk proses tersebut, judul, deskripsi, pengenal posting,
                  nama tampilan penjual jika tersedia, tanggal, platform, dan
                  fakta sumber dapat dikirim ke layanan pemrosesan AI NVIDIA.
                </p>
              </div>
            </section>

            <section>
              <span>04</span>
              <div>
                <h2>Data saat kamu menggunakan situs</h2>
                <p>
                  Infrastruktur situs dapat memproses data teknis standar,
                  seperti alamat IP, jenis perangkat atau peramban, waktu
                  permintaan, halaman yang diminta, dan catatan keamanan. Jika
                  kamu mengirim email, kami juga memproses alamat email dan isi
                  pesan untuk merespons.
                </p>
                <p>
                  Saat kebijakan ini berlaku, RECON belum memasang Google
                  Analytics, akun pengguna, atau pelacak iklan. Jika praktik ini
                  berubah, kebijakan akan diperbarui terlebih dahulu.
                </p>
              </div>
            </section>

            <section>
              <span>05</span>
              <div>
                <h2>Tujuan penggunaan</h2>
                <ul>
                  <li>Menyusun, mencari, dan menampilkan temuan listing.</li>
                  <li>
                    Mengurangi duplikasi dan memperbarui informasi sumber.
                  </li>
                  <li>Menjaga keamanan, keandalan, dan pemecahan masalah.</li>
                  <li>Menjawab pertanyaan, koreksi, dan permintaan privasi.</li>
                </ul>
              </div>
            </section>

            <section>
              <span>06</span>
              <div>
                <h2>Penyimpanan dan penyedia layanan</h2>
                <p>
                  Data dapat diproses pada database, server, pencadangan,
                  layanan AI NVIDIA, serta infrastruktur Cloudflare termasuk R2
                  ketika penyimpanan gambar digunakan. Penyedia dapat beroperasi
                  di luar Indonesia.
                </p>
                <p>
                  Listing dapat tetap tersimpan setelah informasi pada sumber
                  berubah karena pembaruan tidak selalu terjadi seketika. RECON
                  menyimpan data selama dibutuhkan untuk menyediakan,
                  mengamankan, dan memelihara layanan. Jadwal retensi yang lebih
                  rinci masih sedang diformalkan.
                </p>
              </div>
            </section>

            <section>
              <span>07</span>
              <div>
                <h2>Pilihan dan permintaanmu</h2>
                <p>
                  Kamu dapat meminta informasi, koreksi, pembatasan, keberatan,
                  atau penghapusan data yang berkaitan denganmu melalui{" "}
                  <a href="mailto:recon@app-pixel.com">recon@app-pixel.com</a>.
                  Sertakan URL listing RECON atau sumber terkait dan jelaskan
                  permintaanmu. Jangan mengirim KTP atau data sensitif lain
                  kecuali kami memintanya secara proporsional untuk verifikasi.
                </p>
                <p>
                  Penghapusan dari RECON tidak menghapus posting pada platform
                  asal. Untuk perubahan di sana, hubungi platform asal juga.
                </p>
              </div>
            </section>

            <section>
              <span>08</span>
              <div>
                <h2>Keamanan dan perubahan</h2>
                <p>
                  Kami menggunakan langkah teknis dan operasional untuk
                  melindungi data, tetapi tidak ada sistem yang sepenuhnya bebas
                  risiko. Perubahan penting pada praktik ini akan dicatat pada
                  halaman ini bersama tanggal berlakunya.
                </p>
              </div>
            </section>
          </article>
        </div>
      </main>
    </div>
  );
}
