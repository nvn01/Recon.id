import type { Metadata } from "next";

import { EditorialPage } from "~/components/editorial-page";
import { utilityPageRobots } from "~/lib/site";

export const metadata: Metadata = {
  title: "About Us",
  description:
    "Why RECON exists and how its open source secondhand discovery feed works.",
  alternates: { canonical: "/about-us" },
  openGraph: { url: "/about-us" },
  robots: utilityPageRobots,
};

export default function AboutUsPage() {
  return (
    <EditorialPage
      title="ABOUT US"
      introduction="RECON is an open source discovery project built to make scattered secondhand technology listings easier to find."
    >
      <section>
        <h2>Why RECON exists</h2>
        <p>
          Good secondhand computers, components, and gaming gear are spread
          across different platforms, communities, and posting formats.
          Searching each source repeatedly is slow, and useful listings are easy
          to miss.
        </p>
        <p>
          RECON began as a practical way to bring those discoveries into one
          searchable feed while keeping the original source at the center of
          every decision.
        </p>
      </section>

      <section>
        <h2>How it works</h2>
        <p>
          Source connectors find listing information. Automated processing turns
          inconsistent posts into a common structure for category, price,
          condition, location, status, and images. RECON then removes obvious
          duplicates and presents the results in a searchable feed.
        </p>
        <p>
          Every listing points back to the original post. RECON helps you find
          it. The source is where you confirm the current details and contact
          the seller.
        </p>
      </section>

      <section>
        <h2>What RECON is not</h2>
        <p>
          RECON is not a marketplace and does not process payments, arrange
          delivery, inspect items, verify sellers, or guarantee listing
          accuracy. Automated extraction can be wrong and source information can
          change.
        </p>
      </section>

      <section>
        <h2>Open source by design</h2>
        <p>
          The project is open for inspection and contribution on{" "}
          <a
            href="https://github.com/nvn01/Recon.id"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
          </a>
          . Open source development makes the product easier to audit, improve,
          and adapt without turning third-party listing content into RECON
          property.
        </p>
      </section>

      <section>
        <h2>Contact us</h2>
        <p>
          For product questions, corrections, removal requests, or
          collaboration, email{" "}
          <a href="mailto:recon@app-pixel.com">recon@app-pixel.com</a>.
        </p>
      </section>
    </EditorialPage>
  );
}
