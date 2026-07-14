import { z } from "zod";

import { listingSortValues } from "~/data/listing-sort";

const uniqueValues = (values: readonly string[]) =>
  new Set(values).size === values.length;

const boundedText = (maxLength: number) =>
  z.string().trim().min(1).max(maxLength);

const boundedUniqueTextArray = (maxItems: number, maxLength = 80) =>
  z
    .array(boundedText(maxLength))
    .min(1)
    .max(maxItems)
    .refine(uniqueValues, "filter values must be unique");

export const listingPlatformInputSchema = z.enum([
  "reddit",
  "instagram",
  "facebook",
]);

export const listingStatusInputSchema = z.enum([
  "available",
  "unknown",
  "sold",
]);

const platformFiltersSchema = z
  .array(listingPlatformInputSchema)
  .min(1)
  .max(3)
  .refine(uniqueValues, "platform filters must be unique");

const statusFiltersSchema = z
  .array(listingStatusInputSchema)
  .min(1)
  .max(3)
  .refine(uniqueValues, "status filters must be unique");

const priceSchema = z.number().int().min(0).max(2_000_000_000);

export const listingFeedInputSchema = z
  .object({
    platforms: platformFiltersSchema.optional(),
    statuses: statusFiltersSchema.optional(),
    categories: boundedUniqueTextArray(20).optional(),
    locations: boundedUniqueTextArray(10).optional(),
    conditions: boundedUniqueTextArray(10).optional(),
    q: boundedText(80).optional(),
    minPrice: priceSchema.optional(),
    maxPrice: priceSchema.optional(),
    sort: z.enum(listingSortValues).optional(),
    limit: z.number().int().min(1).max(50).default(24),
    cursor: z.string().min(1).max(512).optional(),
    direction: z.literal("forward").optional(),
  })
  .strict()
  .superRefine((input, context) => {
    if (
      input.minPrice !== undefined &&
      input.maxPrice !== undefined &&
      input.minPrice > input.maxPrice
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "minPrice must not exceed maxPrice",
        path: ["minPrice"],
      });
    }
  })
  .default({});

export type ListingFeedInput = z.infer<typeof listingFeedInputSchema>;
export type ListingPlatformInput = z.infer<typeof listingPlatformInputSchema>;
export type ListingStatusInput = z.infer<typeof listingStatusInputSchema>;
