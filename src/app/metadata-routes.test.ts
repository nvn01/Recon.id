import { describe, expect, it } from "vitest";

import manifest from "~/app/manifest";
import robots from "~/app/robots";
import sitemap from "~/app/sitemap";
import { siteConfig } from "~/lib/site";

describe("public indexing metadata routes", () => {
  it("uses the descriptive search identity across site metadata", () => {
    const webManifest = manifest();

    expect(siteConfig.title).toBe(
      "RECON - Cari Barang Secondhand dari Banyak Platform",
    );
    expect(siteConfig.name).toBe("Recon App Indonesia");
    expect(siteConfig.description).toBe(
      "Recon App Indonesia, Temukan barang incaran dengan harga termurah dari berbagai platform jual-beli Indonesia dalam satu tempat.",
    );
    expect(webManifest.name).toBe(siteConfig.title);
    expect(webManifest.description).toBe(siteConfig.description);
  });

  it("publishes only canonical HTTPS URLs without query parameters", () => {
    const entries = sitemap();
    const urls = entries.map((entry) => entry.url);

    expect(urls).toContain("https://recon.app-pixel.com/collection/all");
    expect(urls).toContain("https://recon.app-pixel.com/about-us");
    expect(urls).toContain("https://recon.app-pixel.com/terms");
    expect(urls).toContain("https://recon.app-pixel.com/cookies-policy");
    expect(urls).toContain("https://recon.app-pixel.com/privacy-policy");
    expect(urls).not.toContain("https://recon.app-pixel.com/privacy");
    expect(urls).not.toContain("https://recon.app-pixel.com/cara-kerja");
    expect(urls.every((url) => url.startsWith("https://"))).toBe(true);
    expect(urls.every((url) => !url.includes("?"))).toBe(true);
    expect(new Set(urls).size).toBe(urls.length);
  });

  it("allows the public site while excluding the API", () => {
    expect(robots()).toEqual({
      rules: {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/"],
      },
      sitemap: "https://recon.app-pixel.com/sitemap.xml",
      host: "https://recon.app-pixel.com/",
    });
  });
});
