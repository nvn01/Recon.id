import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { buildContentSecurityPolicy, middleware } from "./middleware";

describe("content security policy", () => {
  it("enforces a nonce without allowing inline scripts", () => {
    const policy = buildContentSecurityPolicy("test-nonce", false);

    expect(policy).toContain("script-src 'self' 'nonce-test-nonce'");
    expect(policy).toContain("script-src-attr 'none'");
    expect(policy).not.toContain("script-src 'self' 'unsafe-inline'");
    expect(policy).toContain("style-src 'self' 'nonce-test-nonce'");
    expect(policy).toContain("style-src-attr 'unsafe-inline'");
    expect(policy).toContain("frame-ancestors 'none'");
    expect(policy).toContain("upgrade-insecure-requests");
  });

  it("uses unsafe-eval only for the development runtime", () => {
    expect(buildContentSecurityPolicy("dev-nonce", true)).toContain(
      "'unsafe-eval'",
    );
    expect(buildContentSecurityPolicy("prod-nonce", false)).not.toContain(
      "'unsafe-eval'",
    );
  });

  it("sets an enforcing response policy with a fresh nonce", () => {
    const request = new NextRequest(
      "https://recon.app-pixel.com/collection/all",
    );
    const firstPolicy = middleware(request).headers.get(
      "Content-Security-Policy",
    );
    const secondPolicy = middleware(request).headers.get(
      "Content-Security-Policy",
    );

    expect(firstPolicy).toMatch(/'nonce-[A-Za-z0-9+/=]+'/);
    expect(secondPolicy).toMatch(/'nonce-[A-Za-z0-9+/=]+'/);
    expect(firstPolicy).not.toBe(secondPolicy);
  });
});
