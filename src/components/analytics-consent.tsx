"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { sanitizedPagePath, trackAnalyticsEvent } from "~/lib/analytics";

type ConsentChoice = "granted" | "denied";

const consentKey = "recon-analytics-consent-v1";
const googleMeasurementId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;
const clarityProjectId = process.env.NEXT_PUBLIC_CLARITY_PROJECT_ID;
const posthogKey = process.env.NEXT_PUBLIC_POSTHOG_KEY;
const posthogHost =
  process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://us.i.posthog.com";

function readConsentChoice(): ConsentChoice | null {
  try {
    const stored = window.localStorage?.getItem(consentKey);
    return stored === "granted" || stored === "denied" ? stored : null;
  } catch {
    return null;
  }
}

function writeConsentChoice(choice: ConsentChoice) {
  try {
    window.localStorage?.setItem(consentKey, choice);
  } catch {
    // The choice still applies for the current page when storage is blocked.
  }
}

function clearConsentChoice() {
  try {
    window.localStorage?.removeItem(consentKey);
  } catch {
    // Reloading still reopens the panel when storage is blocked.
  }
}

function addScript(id: string, src: string) {
  if (document.getElementById(id)) return;
  const script = document.createElement("script");
  script.id = id;
  script.async = true;
  script.src = src;
  document.head.appendChild(script);
}

function removeAnalyticsCookies() {
  const cookieNames = document.cookie
    .split(";")
    .map((item) => item.split("=")[0]?.trim())
    .filter(
      (name): name is string =>
        !!name &&
        (name === "_ga" ||
          name.startsWith("_ga_") ||
          name === "_clck" ||
          name === "_clsk" ||
          name.startsWith("ph_")),
    );

  for (const name of cookieNames) {
    document.cookie = `${name}=; Max-Age=0; path=/; SameSite=Lax`;
  }
}

async function enableAnalytics() {
  if (googleMeasurementId) {
    window.dataLayer = window.dataLayer ?? [];
    window.gtag =
      window.gtag ??
      function gtag(...args: unknown[]) {
        window.dataLayer?.push(args);
      };
    window.gtag("js", new Date());
    window.gtag("consent", "default", {
      analytics_storage: "granted",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
    });
    window.gtag("config", googleMeasurementId, {
      send_page_view: false,
      allow_google_signals: false,
      allow_ad_personalization_signals: false,
    });
    addScript(
      "recon-google-analytics",
      `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(googleMeasurementId)}`,
    );
  }

  if (clarityProjectId) {
    window.clarity =
      window.clarity ??
      function clarity(...args: unknown[]) {
        const queue = (window.clarity as { q?: unknown[] }).q ?? [];
        queue.push(args);
        (window.clarity as { q?: unknown[] }).q = queue;
      };
    window.clarity("consentv2", {
      ad_Storage: "denied",
      analytics_Storage: "granted",
    });
    addScript(
      "recon-microsoft-clarity",
      `https://www.clarity.ms/tag/${encodeURIComponent(clarityProjectId)}`,
    );
  }

  if (posthogKey) {
    const { default: posthog } = await import("posthog-js");
    posthog.init(posthogKey, {
      api_host: posthogHost,
      autocapture: false,
      capture_pageview: false,
      capture_pageleave: false,
      disable_session_recording: true,
      person_profiles: "never",
      persistence: "cookie",
    });
    window.posthog = posthog;
  }
}

export function AnalyticsConsent() {
  const pathname = usePathname();
  const [choice, setChoice] = useState<ConsentChoice | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const initialized = useRef(false);

  useEffect(() => {
    const stored = readConsentChoice();
    if (stored) {
      setChoice(stored);
      setIsOpen(false);
      return;
    }
    setIsOpen(true);
  }, []);

  useEffect(() => {
    if (choice !== "granted" || initialized.current) return;
    initialized.current = true;
    void enableAnalytics();
  }, [choice]);

  useEffect(() => {
    if (choice !== "granted") return;
    const pagePath = sanitizedPagePath(pathname);
    window.gtag?.("event", "page_view", {
      page_location: `${window.location.origin}${pagePath}`,
      page_path: pagePath,
      page_title: document.title,
    });
    window.posthog?.capture("$pageview", {
      $current_url: `${window.location.origin}${pagePath}`,
    });
  }, [choice, pathname]);

  function updateChoice(nextChoice: ConsentChoice) {
    writeConsentChoice(nextChoice);
    setChoice(nextChoice);
    setIsOpen(false);

    if (nextChoice === "denied") {
      window.gtag?.("consent", "update", {
        analytics_storage: "denied",
        ad_storage: "denied",
        ad_user_data: "denied",
        ad_personalization: "denied",
      });
      window.clarity?.("consentv2", {
        ad_Storage: "denied",
        analytics_Storage: "denied",
      });
      window.clarity?.("consent", false);
      if (posthogKey) {
        void import("posthog-js").then(({ default: posthog }) => {
          posthog.opt_out_capturing();
          posthog.reset();
        });
      }
      if (googleMeasurementId) {
        Object.defineProperty(window, `ga-disable-${googleMeasurementId}`, {
          configurable: true,
          value: true,
        });
      }
      removeAnalyticsCookies();
    }

    trackAnalyticsEvent("analytics_consent_updated", {
      analytics: nextChoice,
    });
  }

  if (!isOpen) return null;

  return (
    <section
      className="analytics-consent"
      role="dialog"
      aria-modal="false"
      aria-labelledby="analytics-consent-title"
    >
      <div>
        <p className="eyebrow">Pilihan privasi</p>
        <h2 id="analytics-consent-title">
          Bantu kami memahami penggunaan RECON?
        </h2>
        <p>
          Statistik tambahan hanya aktif jika kamu setuju. Kata pencarian,
          identitas penjual, deskripsi listing, lokasi persis, dan URL sumber
          tidak dikirim. Statistik dasar Cloudflare tetap digunakan untuk
          keamanan dan performa.
        </p>
      </div>
      <div className="analytics-consent-actions">
        <button type="button" onClick={() => updateChoice("denied")}>
          Hanya yang perlu
        </button>
        <button
          type="button"
          className="is-primary"
          onClick={() => updateChoice("granted")}
        >
          Izinkan statistik
        </button>
      </div>
    </section>
  );
}

export function AnalyticsPreferencesButton() {
  return (
    <button
      type="button"
      className="analytics-preferences-button"
      onClick={() => {
        clearConsentChoice();
        window.location.reload();
      }}
    >
      Atur pilihan statistik
    </button>
  );
}
