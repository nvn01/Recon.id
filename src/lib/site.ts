export const siteConfig = {
  name: "RECON",
  url: "https://recon.app-pixel.com",
  title: "RECON - Temukan gear incaranmu",
  description:
    "Temukan listing komputer, komponen, dan gaming gear preloved dari berbagai platform dalam satu feed.",
  email: "recon@app-pixel.com",
  github: "https://github.com/nvn01/Recon.id",
} as const;

export function absoluteUrl(path: string) {
  return new URL(path, siteConfig.url).toString();
}
