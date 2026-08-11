import type { MetadataRoute } from "next";

import { siteConfig } from "~/lib/site";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: siteConfig.name,
    short_name: "RECON",
    description: siteConfig.description,
    start_url: siteConfig.homePath,
    display: "standalone",
    background_color: "#f7f8f6",
    theme_color: "#0b2f20",
    icons: [
      {
        src: "/brand/recon-icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/brand/recon-icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/brand/recon-icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
