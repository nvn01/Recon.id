import type { Metadata } from "next";

import { AnalyticsPreferencesButton } from "~/components/analytics-consent";
import { EditorialPage } from "~/components/editorial-page";

export const metadata: Metadata = {
  title: "Cookies Policy",
  description:
    "How RECON uses necessary storage and optional analytics cookies.",
  alternates: { canonical: "/cookies-policy" },
  openGraph: { url: "/cookies-policy" },
};

export default function CookiesPolicyPage() {
  return (
    <EditorialPage
      title="COOKIES POLICY"
      introduction="This policy explains the browser storage and cookies used by RECON, why they are used, and how you can control optional analytics."
      updated="26 July 2026"
    >
      <section>
        <h2>1. What cookies are</h2>
        <p>
          Cookies are small files stored by a website in your browser. Similar
          browser storage, such as local storage, can remember a preference
          without creating a traditional cookie.
        </p>
      </section>

      <section>
        <h2>2. Necessary storage</h2>
        <p>
          RECON stores your analytics choice in local storage so the consent
          prompt does not appear on every page. Cloudflare may also use strictly
          necessary cookies or technical identifiers to protect the site, manage
          traffic, and maintain performance.
        </p>
        <p>
          Necessary storage is used whether you choose optional analytics or not
          because the site cannot reliably provide security and remember your
          choice without it.
        </p>
      </section>

      <section>
        <h2>3. Optional analytics cookies</h2>
        <p>
          If you select “Izinkan”, RECON may load Google Analytics, Microsoft
          Clarity, and PostHog. Depending on which services are configured, they
          may place cookies or pseudonymous identifiers to measure page views,
          feature use, interactions, device and browser information, and general
          performance.
        </p>
        <p>
          Optional analytics are not loaded before consent. RECON does not
          enable advertising storage or ad personalization through this consent.
        </p>
      </section>

      <section>
        <h2>4. Information excluded from analytics events</h2>
        <p>
          RECON limits its own analytics events to general actions and
          categories. Search terms, seller identities, listing descriptions,
          precise locations, original source URLs, and image URLs are not
          intentionally sent as analytics properties. Listing content is marked
          for masking where Microsoft Clarity is used.
        </p>
      </section>

      <section>
        <h2>5. Your choice</h2>
        <p>
          Choose “Hanya yang perlu” to reject optional analytics, or “Izinkan”
          to allow them. You can change your saved choice at any time.
        </p>
        <AnalyticsPreferencesButton />
      </section>

      <section>
        <h2>6. Browser controls and deletion</h2>
        <p>
          You can also delete cookies and site data through your browser
          settings. Blocking all browser storage may prevent RECON from
          remembering your choice and may affect security-related features.
        </p>
      </section>

      <section>
        <h2>7. Changes and contact</h2>
        <p>
          We may update this policy when our tools or practices change.
          Questions can be sent to{" "}
          <a href="mailto:recon@app-pixel.com">recon@app-pixel.com</a>.
        </p>
      </section>
    </EditorialPage>
  );
}
