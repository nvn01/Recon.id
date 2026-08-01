import { type NextRequest, NextResponse } from "next/server";

const analyticsScriptSources = [
  "https://www.googletagmanager.com",
  "https://www.clarity.ms",
  "https://scripts.clarity.ms",
  "https://static.cloudflareinsights.com",
];

const analyticsConnectSources = [
  "https://www.google-analytics.com",
  "https://*.google-analytics.com",
  "https://www.clarity.ms",
  "https://*.clarity.ms",
  "https://*.posthog.com",
  "https://static.cloudflareinsights.com",
];

export function buildContentSecurityPolicy(
  nonce: string,
  isDevelopment = process.env.NODE_ENV === "development",
) {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}'${isDevelopment ? " 'unsafe-eval'" : ""} ${analyticsScriptSources.join(" ")}`,
    "script-src-attr 'none'",
    `style-src 'self' 'nonce-${nonce}'`,
    "style-src-attr 'unsafe-inline'",
    "img-src 'self' blob: data: https:",
    "font-src 'self' data:",
    `connect-src 'self' ${analyticsConnectSources.join(" ")}`,
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-src 'none'",
    "frame-ancestors 'none'",
    ...(isDevelopment ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");
}

export function middleware(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const contentSecurityPolicy = buildContentSecurityPolicy(nonce);
  const requestHeaders = new Headers(request.headers);

  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", contentSecurityPolicy);

  const response = NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });
  response.headers.set("Content-Security-Policy", contentSecurityPolicy);

  return response;
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|apple-icon.png|icon.svg|manifest.webmanifest|robots.txt|sitemap.xml|opengraph-image).*)",
  ],
};
