const siteUrl = "https://recon.app-pixel.com";
const key = "10d5b5c0377c4f4787e90471c6765a84";
const keyLocation = `${siteUrl}/${key}.txt`;

const sitemapResponse = await fetch(`${siteUrl}/sitemap.xml`);
if (!sitemapResponse.ok) {
  throw new Error(
    `Unable to fetch production sitemap: ${sitemapResponse.status}`,
  );
}

const sitemap = await sitemapResponse.text();
const urlList = Array.from(
  sitemap.matchAll(/<loc>(https:\/\/recon\.app-pixel\.com\/[^<]*)<\/loc>/g),
  (match) => match[1],
).filter(Boolean);

if (urlList.length === 0) {
  throw new Error("Production sitemap did not contain canonical RECON URLs");
}

const response = await fetch("https://api.indexnow.org/indexnow", {
  method: "POST",
  headers: { "content-type": "application/json; charset=utf-8" },
  body: JSON.stringify({
    host: "recon.app-pixel.com",
    key,
    keyLocation,
    urlList,
  }),
});

if (!response.ok) {
  throw new Error(`IndexNow submission failed: ${response.status}`);
}

console.log(`Submitted ${urlList.length} canonical URLs to IndexNow.`);
