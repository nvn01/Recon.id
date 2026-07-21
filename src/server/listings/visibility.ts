import { Prisma } from "../../../generated/prisma";

export const publicListingModerationJoins = Prisma.sql`
  LEFT JOIN listing_moderation AS listing_moderation
    ON listing_moderation.listing_id = listing.id
  LEFT JOIN platform_controls AS platform_control
    ON platform_control.platform = listing.platform
`;

export const publicListingVisibilityFilter = Prisma.sql`
  AND COALESCE(platform_control.public_visible, TRUE)
  AND NOT COALESCE(listing_moderation.hidden, FALSE)
  AND NOT (
    listing.platform::text = 'facebook'
    AND EXISTS (
      SELECT 1
      FROM facebook_seller_flags AS seller_flag
      WHERE seller_flag.status::text = 'blocked'
        AND seller_flag.normalized_seller_name = normalize_seller_name(
          COALESCE(listing_moderation.seller_name_override, listing.seller_name)
        )
    )
  )
`;
