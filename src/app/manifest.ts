import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "RECON - Temukan gear incaranmu",
    short_name: "RECON",
    description:
      "Temukan listing komputer, komponen, dan gaming gear preloved dari berbagai platform dalam satu feed.",
    start_url: "/collection/all",
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
