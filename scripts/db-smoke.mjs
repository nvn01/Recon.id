import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const {
  ListingPlatform,
  ListingStatus,
  Prisma,
  PrismaClient,
} = require("../generated/prisma");

const db = new PrismaClient();
const sourceUrl = "https://example.test/recon/db-smoke";

async function main() {
  const listing = await db.listing.upsert({
    where: { sourceUrl },
    create: {
      platform: ListingPlatform.REDDIT,
      sourceUrl,
      externalId: "db-smoke",
      title: "Recon DB smoke listing",
      description: "Fixture row created by scripts/db-smoke.mjs.",
      category: "RAM",
      brand: "ADATA",
      price: 1500000,
      locationTexts: ["Jakarta", "Bekasi"],
      conditionText: "used",
      sellerName: "recon-smoke",
      status: ListingStatus.AVAILABLE,
      images: {
        create: {
          sourceUrl: "https://example.test/recon/db-smoke.jpg",
          position: 0,
          altText: "Smoke test image",
        },
      },
    },
    update: {
      lastFetchedAt: new Date(),
    },
  });

  await db.listingImage.deleteMany({
    where: { listingId: listing.id },
  });

  await db.listingImage.create({
    data: {
      listingId: listing.id,
      sourceUrl: "https://example.test/recon/db-smoke.jpg",
      position: 0,
      altText: "Smoke test image",
    },
  });

  const loaded = await db.listing.findUniqueOrThrow({
    where: { sourceUrl },
    include: {
      images: {
        orderBy: { position: "asc" },
      },
    },
  });

  if (loaded.platform !== ListingPlatform.REDDIT) {
    throw new Error(`Unexpected platform: ${loaded.platform}`);
  }

  if (loaded.status !== ListingStatus.AVAILABLE) {
    throw new Error(`Unexpected status: ${loaded.status}`);
  }

  if (loaded.category !== "RAM" || loaded.brand !== "ADATA") {
    throw new Error(`Unexpected category/brand: ${loaded.category}/${loaded.brand}`);
  }

  if (loaded.locationTexts.length !== 2) {
    throw new Error(`Expected two locations, found ${loaded.locationTexts.length}`);
  }

  if (loaded.images.length !== 1) {
    throw new Error(`Expected one image, found ${loaded.images.length}`);
  }

  try {
    await db.listing.create({
      data: {
        platform: ListingPlatform.REDDIT,
        sourceUrl,
        title: "Duplicate smoke listing",
        description: "This insert should fail on source_url uniqueness.",
        status: ListingStatus.UNKNOWN,
      },
    });
    throw new Error("Duplicate sourceUrl insert unexpectedly succeeded");
  } catch (error) {
    if (
      !(error instanceof Prisma.PrismaClientKnownRequestError) ||
      error.code !== "P2002"
    ) {
      throw error;
    }
  }

  console.log(
    `DB smoke passed: listing=${loaded.id}, images=${loaded.images.length}`,
  );
}

try {
  await main();
} finally {
  await db.listing.deleteMany({
    where: { sourceUrl },
  });
  await db.$disconnect();
}
