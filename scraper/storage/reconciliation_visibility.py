"""Public-visibility SQL shared by bounded listing reconciliation jobs."""

from __future__ import annotations


def reconciliation_visibility_filter(listing_alias: str, *, include_facebook_seller: bool) -> str:
    """Return the public-feed visibility predicate for a trusted SQL alias."""
    if listing_alias not in {"listing"}:
        raise ValueError("unsupported reconciliation listing alias")

    seller_filter = ""
    if include_facebook_seller:
        seller_filter = f"""
  AND NOT EXISTS (
      SELECT 1
      FROM facebook_seller_flags AS seller_flag
      WHERE seller_flag.status::text = 'blocked'
        AND seller_flag.normalized_seller_name = normalize_seller_name(
          COALESCE(
            (SELECT moderation.seller_name_override
             FROM listing_moderation AS moderation
             WHERE moderation.listing_id = {listing_alias}.id),
            {listing_alias}.seller_name
          )
        )
  )"""

    return f"""
  AND COALESCE(
      (SELECT control.public_visible
       FROM platform_controls AS control
       WHERE control.platform = {listing_alias}.platform),
      TRUE
  )
  AND NOT COALESCE(
      (SELECT moderation.hidden
       FROM listing_moderation AS moderation
       WHERE moderation.listing_id = {listing_alias}.id),
      FALSE
  )
  AND NOT EXISTS (
      SELECT 1
      FROM listing_content_blocks AS content_block
      WHERE content_block.platform = {listing_alias}.platform
        AND content_block.field::text = 'title'
        AND content_block.normalized_value = normalize_listing_content({listing_alias}.title)
  )
  AND NOT EXISTS (
      SELECT 1
      FROM listing_content_blocks AS content_block
      WHERE content_block.platform = {listing_alias}.platform
        AND content_block.field::text = 'description'
        AND content_block.normalized_value = normalize_listing_content({listing_alias}.description)
  ){seller_filter}
"""


FACEBOOK_RECONCILIATION_VISIBILITY_SQL = reconciliation_visibility_filter(
    "listing",
    include_facebook_seller=True,
)
REDDIT_RECONCILIATION_VISIBILITY_SQL = reconciliation_visibility_filter(
    "listing",
    include_facebook_seller=False,
)
