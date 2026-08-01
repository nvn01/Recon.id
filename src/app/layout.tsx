import "~/styles/globals.css";

import { type Metadata, type Viewport } from "next";
import { Bricolage_Grotesque, Geist, Geist_Mono } from "next/font/google";
import { headers } from "next/headers";

import { AnalyticsConsent } from "~/components/analytics-consent";
import { SiteFooter } from "~/components/site-footer";
import { siteConfig } from "~/lib/site";
import { TRPCReactProvider } from "~/trpc/react";

export const metadata: Metadata = {
  metadataBase: new URL(siteConfig.url),
  applicationName: "RECON",
  title: {
    default: siteConfig.title,
    template: "%s - RECON",
  },
  description: siteConfig.description,
  category: "technology",
  keywords: [
    "barang bekas",
    "komputer bekas",
    "laptop bekas",
    "GPU bekas",
    "gaming gear",
    "Indonesia",
  ],
  authors: [{ name: "RECON", url: siteConfig.url }],
  creator: "RECON",
  publisher: "RECON",
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  openGraph: {
    type: "website",
    locale: "id_ID",
    siteName: "RECON",
    title: siteConfig.title,
    description: siteConfig.description,
    url: "/collection/all",
    images: [
      {
        url: "/opengraph-image",
        width: 1200,
        height: 630,
        alt: "RECON - Temukan gear incaranmu",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: siteConfig.title,
    description: siteConfig.description,
    images: ["/opengraph-image"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
  appleWebApp: {
    capable: true,
    title: "RECON",
    statusBarStyle: "black-translucent",
  },
};

export const viewport: Viewport = {
  themeColor: "#0b2f20",
};

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist-sans",
});

const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-bricolage",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
});

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": `${siteConfig.url}/#organization`,
        name: siteConfig.name,
        url: siteConfig.url,
        email: siteConfig.email,
        sameAs: [siteConfig.github],
      },
      {
        "@type": "WebSite",
        "@id": `${siteConfig.url}/#website`,
        url: siteConfig.url,
        name: siteConfig.name,
        description: siteConfig.description,
        inLanguage: "id-ID",
        publisher: { "@id": `${siteConfig.url}/#organization` },
      },
    ],
  };

  return (
    <html
      lang="id"
      className={`${geist.variable} ${bricolage.variable} ${geistMono.variable}`}
    >
      <body>
        <script
          nonce={nonce}
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(structuredData).replace(/</g, "\\u003c"),
          }}
        />
        <TRPCReactProvider>
          {children}
          <SiteFooter />
          <AnalyticsConsent />
        </TRPCReactProvider>
      </body>
    </html>
  );
}
