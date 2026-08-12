-- Least-privilege reads required by scraper reconciliation visibility checks.
-- Run through the existing owner-controlled role-grants step with scraper_user set.
GRANT SELECT (platform, public_visible)
  ON TABLE public.platform_controls TO :"scraper_user";
GRANT SELECT (listing_id, hidden, seller_name_override)
  ON TABLE public.listing_moderation TO :"scraper_user";
GRANT SELECT (platform, field, normalized_value)
  ON TABLE public.listing_content_blocks TO :"scraper_user";
GRANT SELECT (normalized_seller_name, status)
  ON TABLE public.facebook_seller_flags TO :"scraper_user";
