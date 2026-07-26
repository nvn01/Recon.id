export const siteConfig = {
  name: "RECON",
  url: "https://recon.app-pixel.com",
  title: "RECON - Temukan gear incaranmu",
  description:
    "Temukan listing komputer, komponen, dan gaming gear preloved dari berbagai platform dalam satu feed.",
  email: "recon@app-pixel.com",
  github: "https://github.com/nvn01/Recon.id",
  cloudflareAnalyticsToken: "8ff7736c55c0442487a1c7e24a2ee048",
} as const;

export function absoluteUrl(path: string) {
  return new URL(path, siteConfig.url).toString();
}
