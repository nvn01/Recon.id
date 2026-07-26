import { DiscordLogo, XLogo } from "@phosphor-icons/react/dist/ssr";
import Image from "next/image";
import Link from "next/link";

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
            Open source secondhand discovery. Temukan barang incaranmu dalam
            satu platform.
          </p>
        </div>

        <nav className="footer-links" aria-label="Informasi RECON">
          <Link href="/about-us">About us</Link>
          <Link href="/terms">Terms</Link>
          <Link href="/cookies-policy">Cookies policy</Link>
          <Link href="/privacy-policy">Privacy policy</Link>
        </nav>

        <div className="footer-contact">
          <a href="mailto:recon@app-pixel.com">Contact us</a>
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
              aria-label="X, akun segera hadir"
              title="X, segera hadir"
            >
              <XLogo aria-hidden="true" weight="fill" />
            </span>
            <span
              className="social-placeholder"
              role="img"
              aria-label="Discord, komunitas segera hadir"
              title="Discord, segera hadir"
            >
              <DiscordLogo aria-hidden="true" weight="fill" />
            </span>
          </div>
        </div>
      </div>

      <div className="site-footer-meta">
        <span>© {new Date().getFullYear()} RECON</span>
        <span>
          Selalu cross-check barang dan postingan sebelum bertransaksi · Recon
          tidak bertanggung jawab atas ketidaksesuaian barang yang dijual
        </span>
      </div>
    </footer>
  );
}
