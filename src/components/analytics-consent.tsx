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

function addScript(id: string, src: string) {
  if (document.getElementById(id)) return;
  const script = document.createElement("script");
  script.id = id;
  script.async = true;
  script.src = src;
  document.head.appendChild(script);
}

function loadScript(id: string, src: string) {
  return new Promise<void>((resolve, reject) => {
    const existing = document.getElementById(id);
    if (existing) {
      resolve();
      return;
    }

    const script = document.createElement("script");
    script.id = id;
    script.async = true;
    script.src = src;
    script.addEventListener("load", () => resolve(), { once: true });
    script.addEventListener(
      "error",
      () => reject(new Error(`Unable to load analytics script: ${id}`)),
      { once: true },
    );
    document.head.appendChild(script);
  });
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
    Object.defineProperty(window, `ga-disable-${googleMeasurementId}`, {
      configurable: true,
      value: false,
    });
    window.dataLayer = window.dataLayer ?? [];
    window.gtag =
      window.gtag ??
      function gtag(...args: unknown[]) {
        window.dataLayer?.push(args);
      };
    window.gtag("consent", "default", {
      analytics_storage: "denied",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
    });
    window.gtag("js", new Date());
    window.gtag("consent", "update", {
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
    await loadScript(
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
    if (window.posthog) {
      window.posthog.opt_in_capturing();
    } else {
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
      posthog.opt_in_capturing();
      window.posthog = posthog;
    }
  }
}

function disableAnalytics() {
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
  if (posthogKey && window.posthog) {
    window.posthog.opt_out_capturing();
    window.posthog.reset();
  }
  if (googleMeasurementId) {
    Object.defineProperty(window, `ga-disable-${googleMeasurementId}`, {
      configurable: true,
      value: true,
    });
  }
  removeAnalyticsCookies();
}

export function AnalyticsConsent() {
  const pathname = usePathname();
  const [choice, setChoice] = useState<ConsentChoice | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [analyticsReady, setAnalyticsReady] = useState(false);
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
    function openPreferences() {
      setIsOpen(true);
    }

    window.addEventListener(
      "recon:open-analytics-preferences",
      openPreferences,
    );
    return () => {
      window.removeEventListener(
        "recon:open-analytics-preferences",
        openPreferences,
      );
    };
  }, []);

  useEffect(() => {
    if (choice !== "granted" || initialized.current) return;
    initialized.current = true;
    void enableAnalytics()
      .then(() => setAnalyticsReady(true))
      .catch(() => {
        initialized.current = false;
      });
  }, [choice]);

  useEffect(() => {
    if (choice !== "granted" || !analyticsReady) return;
    const pagePath = sanitizedPagePath(pathname);
    window.gtag?.("event", "page_view", {
      page_location: `${window.location.origin}${pagePath}`,
      page_path: pagePath,
      page_title: document.title,
    });
    window.posthog?.capture("$pageview", {
      $current_url: `${window.location.origin}${pagePath}`,
    });
  }, [analyticsReady, choice, pathname]);

  function updateChoice(nextChoice: ConsentChoice) {
    writeConsentChoice(nextChoice);
    setChoice(nextChoice);
    setIsOpen(false);

    if (nextChoice === "denied") {
      setAnalyticsReady(false);
      disableAnalytics();
    }

    trackAnalyticsEvent("analytics_consent_updated", {
      analytics: nextChoice,
    });
  }

  if (!isOpen) return null;

  return (
    <section
      className="recon-privacy-choice"
      role="dialog"
      aria-modal="false"
      aria-describedby="analytics-consent-copy"
    >
      <p id="analytics-consent-copy">
        Izinkan cookie statistik untuk membantu kami meningkatkan RECON?
      </p>
      <div className="recon-privacy-choice-actions">
        <button type="button" onClick={() => updateChoice("denied")}>
          Hanya yang perlu
        </button>
        <button
          type="button"
          className="is-primary"
          onClick={() => updateChoice("granted")}
        >
          Izinkan
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
      onClick={() =>
        window.dispatchEvent(new Event("recon:open-analytics-preferences"))
      }
    >
      Manage cookie preferences
    </button>
  );
}
