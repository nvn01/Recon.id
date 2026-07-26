import type { Metadata } from "next";

import { EditorialPage } from "~/components/editorial-page";

export const metadata: Metadata = {
  title: "Terms",
  description: "The terms that apply when you access and use RECON.",
  alternates: { canonical: "/terms" },
  openGraph: { url: "/terms" },
};

export default function TermsPage() {
  return (
    <EditorialPage
      title="LEGAL TERMS"
      introduction="These terms explain what RECON provides, what it does not verify, and the responsibilities you accept when using the service."
      updated="26 July 2026"
    >
      <section>
        <h2>1. Acceptance and scope</h2>
        <p>
          By accessing or using RECON, you agree to these terms. If you do not
          agree, do not use the service. These terms apply to the RECON website,
          public feed, and related features.
        </p>
      </section>

      <section>
        <h2>2. What RECON provides</h2>
        <p>
          RECON is an independent, open source discovery service for secondhand
          technology and gaming gear. It gathers and organizes information found
          on third-party sources, then links you back to the original post.
        </p>
        <p>
          RECON is not a marketplace, seller, broker, payment provider, delivery
          service, escrow service, or party to any transaction.
        </p>
      </section>

      <section>
        <h2>3. Third-party listings and services</h2>
        <p>
          Listings, seller details, images, descriptions, prices, availability,
          and linked services are supplied by third parties. Their own terms,
          policies, and intellectual property rights continue to apply.
        </p>
        <p>
          A link or listing appearing on RECON does not mean that RECON endorses
          the seller, verifies ownership, or has permission to make promises on
          that third party&apos;s behalf.
        </p>
      </section>

      <section>
        <h2>4. Your responsibility before a transaction</h2>
        <p>
          You are responsible for opening the original post and checking the
          seller, item, price, condition, authenticity, ownership, location,
          warranty, payment method, delivery method, and current availability.
        </p>
        <p>
          Use a safe meeting and payment process. Do not send money or personal
          documents until you have independently assessed the transaction.
        </p>
      </section>

      <section>
        <h2>5. Accuracy and availability</h2>
        <p>
          RECON uses automated collection and processing. Information may be
          incomplete, duplicated, delayed, incorrectly categorized, or no longer
          available. A displayed date may be the original posting date or the
          date RECON first found the listing.
        </p>
        <p>
          We may change, suspend, remove, or discontinue any part of the service
          without guaranteeing uninterrupted access.
        </p>
      </section>

      <section>
        <h2>6. Acceptable use</h2>
        <p>
          You may use RECON for lawful discovery and research. You must not
          disrupt the service, bypass security controls, introduce malicious
          code, misuse personal data, impersonate another person, or use RECON
          to facilitate fraud or other unlawful activity.
        </p>
      </section>

      <section>
        <h2>7. Open source software</h2>
        <p>
          RECON&apos;s source code is available through its public GitHub
          repository. Any license and notices published with that repository
          govern permitted use of the code. Source availability does not grant
          rights to third-party listing content, seller information,
          source-platform branding, or other material that RECON does not own.
        </p>
      </section>

      <section>
        <h2>8. Disclaimer and limitation</h2>
        <p>
          RECON is provided on an as-available basis. To the extent permitted by
          applicable law, RECON is not responsible for losses caused by a
          seller, buyer, third-party platform, inaccurate listing, failed
          transaction, counterfeit item, payment, delivery, or use of external
          links.
        </p>
        <p>
          Nothing in these terms excludes rights or responsibilities that cannot
          legally be excluded.
        </p>
      </section>

      <section>
        <h2>9. Changes to these terms</h2>
        <p>
          We may update these terms when the service or applicable requirements
          change. The revised version will be published here with a new
          effective date. Continued use after an update means you accept the
          revised terms.
        </p>
      </section>

      <section>
        <h2>10. Contact</h2>
        <p>
          Questions about these terms can be sent to{" "}
          <a href="mailto:recon@app-pixel.com">recon@app-pixel.com</a>.
        </p>
      </section>
    </EditorialPage>
  );
}
