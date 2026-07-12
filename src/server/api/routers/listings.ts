import { TRPCError } from "@trpc/server";

import { createTRPCRouter, publicProcedure } from "~/server/api/trpc";
import { InvalidListingCursorError } from "~/server/listings/cursor";
import { listingFeedInputSchema } from "~/server/listings/feed-input";
import { getListingFeed } from "~/server/listings/feed";

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
        throw error;
      }
    }),
});
