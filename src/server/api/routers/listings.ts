import { TRPCError } from "@trpc/server";

import { createTRPCRouter, publicProcedure } from "~/server/api/trpc";
import { InvalidListingCursorError } from "~/server/listings/cursor";
import { listingFeedInputSchema } from "~/server/listings/feed-input";
import { getListingFeed } from "~/server/listings/feed";
import { getListingFacets } from "~/server/listings/facets";
import { getListingVersion } from "~/server/listings/version";

export const listingsRouter = createTRPCRouter({
  feed: publicProcedure
    .input(listingFeedInputSchema)
    .query(async ({ ctx, input }) => {
      try {
        return await getListingFeed(ctx.db, input);
      } catch (error) {
        if (error instanceof InvalidListingCursorError) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Invalid listing feed cursor",
          });
        }

        console.error("[listings.feed] unexpected failure", {
          name: error instanceof Error ? error.name : "UnknownError",
        });
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "Unable to load listing feed",
        });
      }
    }),
  facets: publicProcedure.query(async ({ ctx }) => {
    try {
      return await getListingFacets(ctx.db);
    } catch (error) {
      console.error("[listings.facets] unexpected failure", {
        name: error instanceof Error ? error.name : "UnknownError",
      });
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message: "Unable to load listing filters",
      });
    }
  }),
  version: publicProcedure.query(async ({ ctx }) => {
    try {
      return await getListingVersion(ctx.db);
    } catch (error) {
      console.error("[listings.version] unexpected failure", {
        name: error instanceof Error ? error.name : "UnknownError",
      });
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message: "Unable to check for new listings",
      });
    }
  }),
});
