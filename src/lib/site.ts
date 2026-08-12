export const siteConfig = {
  name: "Recon App Indonesia",
  url: "https://recon.app-pixel.com",
  homePath: "/",
  title: "RECON - Cari Barang Secondhand dari Banyak Platform",
  description:
    "Recon App Indonesia, Temukan barang incaran dengan harga termurah dari berbagai platform jual-beli Indonesia dalam satu tempat.",
  email: "recon@app-pixel.com",
  github: "https://github.com/nvn01/Recon.id",
  x: "https://x.com/ofpSoftware",
} as const;

export const siteIdentityStructuredData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": `${siteConfig.url}/#organization`,
      name: siteConfig.name,
      url: siteConfig.url,
      email: siteConfig.email,
      sameAs: [siteConfig.github, siteConfig.x],
    },
    {
      "@type": "WebSite",
      "@id": `${siteConfig.url}/#website`,
      url: new URL(siteConfig.homePath, siteConfig.url).toString(),
      name: siteConfig.name,
      alternateName: ["RECON"],
      description: siteConfig.description,
      inLanguage: "id-ID",
      publisher: { "@id": `${siteConfig.url}/#organization` },
    },
  ],
} as const;

export const utilityPageRobots = { index: false, follow: true } as const;

export function absoluteUrl(path: string) {
  return new URL(path, siteConfig.url).toString();
}
