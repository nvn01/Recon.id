export const siteConfig = {
  name: "RECON",
  url: "https://recon.app-pixel.com",
  title: "RECON - Cari Barang Secondhand dari Banyak Platform",
  description:
    "Cari laptop, GPU, komponen PC, gaming gear, dan ponsel secondhand dari berbagai platform jual-beli Indonesia dalam satu tempat.",
  email: "recon@app-pixel.com",
  github: "https://github.com/nvn01/Recon.id",
} as const;

export function absoluteUrl(path: string) {
  return new URL(path, siteConfig.url).toString();
}
