import type { Metadata } from "next";

import { EditorialPage } from "~/components/editorial-page";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "How RECON processes listing information, technical data, and privacy requests.",
  alternates: { canonical: "/privacy-policy" },
  openGraph: { url: "/privacy-policy" },
};

export default function PrivacyPolicyPage() {
  return (
    <EditorialPage
      title="PRIVACY POLICY"
      introduction="This policy explains the information RECON processes to operate its discovery feed, protect the site, and respond to requests."
      updated="26 July 2026"
    >
      <section>
        <h2>1. Who operates RECON</h2>
        <p>
          RECON operates this website and discovery feed. Privacy questions,
          corrections, and removal requests can be sent to{" "}
          <a href="mailto:recon@app-pixel.com">recon@app-pixel.com</a>.
        </p>
      </section>

      <section>
        <h2>2. Listing information we process</h2>
        <p>
          Depending on the source, RECON may process a listing title,
          description, price, category, brand, condition, status, general
          location, seller display name, posting or discovery date, source link,
          post identifier, images, and related source facts.
        </p>
        <p>
          This information comes from third-party services. Public availability
          does not remove privacy, copyright, or platform rights that may apply
          to the information.
        </p>
      </section>

      <section>
        <h2>3. Automated processing</h2>
        <p>
          RECON uses automated processing to identify likely listings and
          organize details such as title, price, category, condition, general
          location, and status. Automated results may be wrong.
        </p>
        <p>
          For this process, listing text, post identifiers, seller display names
          when available, dates, platform names, and source facts may be sent to
          NVIDIA AI processing services.
        </p>
      </section>

      <section>
        <h2>4. Information generated when you use the site</h2>
        <p>
          Site infrastructure may process standard technical information such as
          IP address, device and browser type, request time, requested page, and
          security logs. If you contact us, we process your email address and
          message to respond.
        </p>
        <p>
          Cloudflare provides infrastructure, security, and basic traffic or
          performance information. Optional Google Analytics, Microsoft Clarity,
          and PostHog services load only after consent. See the{" "}
          <a href="/cookies-policy">Cookies Policy</a> for details and controls.
        </p>
      </section>

      <section>
        <h2>5. Why we use information</h2>
        <ul>
          <li>
            To collect, organize, search, and display listing discoveries.
          </li>
          <li>To reduce duplicates and refresh source information.</li>
          <li>To secure, maintain, measure, and troubleshoot the service.</li>
          <li>To answer questions, corrections, and privacy requests.</li>
        </ul>
      </section>

      <section>
        <h2>6. Service providers and international processing</h2>
        <p>
          Information may be processed through RECON databases, servers,
          backups, NVIDIA AI services, and Cloudflare infrastructure, including
          R2 when image storage is used. Optional analytics may be processed by
          Google, Microsoft, and PostHog. Providers may operate outside
          Indonesia.
        </p>
      </section>

      <section>
        <h2>7. Retention</h2>
        <p>
          Listings may remain in RECON after a source changes because updates
          are not always immediate. We retain information for as long as
          reasonably needed to provide, secure, maintain, and improve the
          service, respond to requests, and meet applicable obligations.
        </p>
      </section>

      <section>
        <h2>8. Your requests</h2>
        <p>
          You may ask for access, correction, restriction, objection, or
          deletion of information related to you. Email{" "}
          <a href="mailto:recon@app-pixel.com">recon@app-pixel.com</a> and
          include the relevant RECON or source URL with a clear description of
          your request. Do not send an identity document or other sensitive
          information unless proportionate verification is requested.
        </p>
        <p>
          Removing information from RECON does not remove the original post from
          its source platform. Contact that platform for changes to the original
          post.
        </p>
      </section>

      <section>
        <h2>9. Security and changes</h2>
        <p>
          We use technical and operational measures intended to protect
          information, but no system is risk-free. Material changes to this
          policy will be published here with an updated effective date.
        </p>
      </section>
    </EditorialPage>
  );
}
