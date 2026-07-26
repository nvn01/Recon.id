import Image from "next/image";
import Link from "next/link";

function XIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M18.9 2.5h3.7l-8.1 9.2L24 21.5h-7.4l-5.8-7.6-6.7 7.6H.4l8.7-9.9L0 2.5h7.6l5.3 7 6-7Zm-1.3 17h2L6.5 4.4H4.4l13.2 15.1Z" />
    </svg>
  );
}

function DiscordIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M19.5 5.3A18 18 0 0 0 15 3.9l-.6 1.3a16.7 16.7 0 0 0-4.9 0l-.6-1.3a18.6 18.6 0 0 0-4.5 1.4C1.6 9.5.8 13.6 1.2 17.6a18.2 18.2 0 0 0 5.5 2.8L8 18.6a11.7 11.7 0 0 1-2.1-1l.5-.4c4 1.8 8.3 1.8 12.2 0l.6.4c-.7.4-1.4.7-2.2 1l1.3 1.8a18.2 18.2 0 0 0 5.5-2.8c.5-4.7-.8-8.8-4.3-12.3ZM8.5 15.2c-1.2 0-2.2-1.1-2.2-2.5s1-2.5 2.2-2.5c1.2 0 2.2 1.1 2.2 2.5 0 1.4-1 2.5-2.2 2.5Zm7 0c-1.2 0-2.2-1.1-2.2-2.5s1-2.5 2.2-2.5c1.2 0 2.2 1.1 2.2 2.5 0 1.4-1 2.5-2.2 2.5Z" />
    </svg>
  );
}

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <div className="footer-brand">
          <Link href="/collection/all" className="footer-wordmark">
            <Image
              src="/brand/recon-mark-forest.svg"
              alt=""
              width={24}
              height={24}
            />
            <span>RECON</span>
          </Link>
          <p>
            Ringkasan temuan dari sumber pihak ketiga. Selalu periksa posting
            asal sebelum bertransaksi.
          </p>
        </div>

        <nav className="footer-links" aria-label="Informasi RECON">
          <p>Kenali RECON</p>
          <Link href="/cara-kerja">Cara kerja &amp; batasan</Link>
          <Link href="/privacy">Privasi</Link>
        </nav>

        <div className="footer-contact">
          <p>Terlibat</p>
          <a href="mailto:recon@app-pixel.com">recon@app-pixel.com</a>
          <a
            href="https://github.com/nvn01/Recon.id"
            target="_blank"
            rel="noreferrer"
          >
            Kontribusi di GitHub ↗
          </a>
          <div
            className="footer-socials"
            aria-label="Media sosial segera hadir"
          >
            <span
              className="social-placeholder"
              role="img"
              aria-label="X — akun segera hadir"
              title="X — segera hadir"
            >
              <XIcon />
            </span>
            <span
              className="social-placeholder"
              role="img"
              aria-label="Discord — komunitas segera hadir"
              title="Discord — segera hadir"
            >
              <DiscordIcon />
            </span>
          </div>
        </div>
      </div>

      <div className="site-footer-meta">
        <span>© {new Date().getFullYear()} RECON</span>
        <span>Layanan discovery independen · bukan marketplace</span>
      </div>
    </footer>
  );
}
