"use client";

export type AnalyticsEventName =
  | "collection_viewed"
  | "platform_viewed"
  | "search_submitted"
  | "filter_applied"
  | "listing_opened"
  | "original_source_clicked"
  | "load_more_clicked"
  | "privacy_viewed"
  | "cara_kerja_viewed"
  | "analytics_consent_updated";

export type AnalyticsProperties = Record<
  string,
  string | number | boolean | null | undefined
>;

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
    clarity?: (...args: unknown[]) => void;
    posthog?: {
      capture: (name: string, properties?: AnalyticsProperties) => void;
      opt_in_capturing: () => void;
      opt_out_capturing: () => void;
      reset: () => void;
    };
  }
}

export function sanitizedPagePath(pathname: string) {
  return pathname.startsWith("/") ? pathname : "/";
}

export function queryLengthBucket(length: number) {
  if (length <= 0) return "0";
  if (length <= 5) return "1-5";
  if (length <= 15) return "6-15";
  if (length <= 30) return "16-30";
  return "31-80";
}

export function resultCountBucket(count: number) {
  if (count <= 0) return "0";
  if (count <= 5) return "1-5";
  if (count <= 12) return "6-12";
  if (count <= 24) return "13-24";
  return "25+";
}

export function priceBucket(price: number | null) {
  if (price === null) return "unknown";
  if (price < 500_000) return "<500k";
  if (price < 1_500_000) return "500k-1.5m";
  if (price < 5_000_000) return "1.5m-5m";
  if (price < 15_000_000) return "5m-15m";
  return "15m+";
}

export function trackAnalyticsEvent(
  name: AnalyticsEventName,
  properties: AnalyticsProperties = {},
) {
  if (typeof window === "undefined") return;

  window.gtag?.("event", name, properties);
  window.clarity?.("event", name);
  window.posthog?.capture(name, properties);
}

export function openAnalyticsPreferences() {
  window.dispatchEvent(new Event("recon:open-analytics-preferences"));
}
