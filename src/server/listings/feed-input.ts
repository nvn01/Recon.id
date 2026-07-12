import { z } from "zod";

const uniqueValues = (values: readonly string[]) =>
  new Set(values).size === values.length;

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

export const listingFeedInputSchema = z
  .object({
    platforms: platformFiltersSchema.optional(),
    statuses: statusFiltersSchema.optional(),
    limit: z.number().int().min(1).max(50).default(24),
    cursor: z.string().min(1).max(512).optional(),
  })
  .strict()
  .default({});

export type ListingFeedInput = z.infer<typeof listingFeedInputSchema>;
export type ListingPlatformInput = z.infer<typeof listingPlatformInputSchema>;
export type ListingStatusInput = z.infer<typeof listingStatusInputSchema>;
