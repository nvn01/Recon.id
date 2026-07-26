import { ImageResponse } from "next/og";

export const alt = "RECON - Temukan gear incaranmu";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div
      style={{
        alignItems: "stretch",
        background: "#0b2f20",
        color: "#f3f5ee",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        justifyContent: "space-between",
        padding: "72px 82px",
        width: "100%",
      }}
    >
      <div
        style={{
          alignItems: "center",
          display: "flex",
          fontSize: 34,
          fontWeight: 700,
          gap: 18,
          letterSpacing: 2,
        }}
      >
        <span
          style={{
            alignItems: "center",
            background: "#d7ff64",
            borderRadius: 999,
            color: "#0b2f20",
            display: "flex",
            height: 54,
            justifyContent: "center",
            width: 54,
          }}
        >
          R
        </span>
        RECON
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <div
          style={{
            display: "flex",
            fontSize: 82,
            fontWeight: 700,
            letterSpacing: -4,
            lineHeight: 1.02,
            maxWidth: 950,
          }}
        >
          Gear bagus muncul sebentar.
        </div>
        <div
          style={{
            color: "#cbd8cf",
            display: "flex",
            fontSize: 29,
            maxWidth: 900,
          }}
        >
          Temukan listing komputer dan gaming gear preloved dari berbagai
          platform dalam satu feed.
        </div>
      </div>
      <div
        style={{
          color: "#d7ff64",
          display: "flex",
          fontSize: 24,
          letterSpacing: 1,
        }}
      >
        recon.app-pixel.com
      </div>
    </div>,
    size,
  );
}
