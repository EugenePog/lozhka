import type { Config } from "tailwindcss";
import tokens from "../../packages/design-tokens/tokens.json";

// Single source: packages/design-tokens/tokens.json (from the GUI requirements, section 2).
const c = tokens.color;
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        cream: c.background, green: c.primaryGreen, terra: c.actionTerracotta, logo: c.logoTerracotta,
        "terra-tint": c.terracottaTint, "terra-tint-text": c.terracottaTintText, "green-tint": c.greenTint,
        muted: c.mutedText, line: c.border, "form-line": c.formBorder, card: c.card,
        "ph-from": c.photoPlaceholderFrom, "ph-to": c.photoPlaceholderTo,
      },
      fontFamily: { sans: ["Nunito", "ui-rounded", "system-ui", "sans-serif"] },
      borderRadius: { card: `${tokens.radius.card}px`, image: `${tokens.radius.image}px`, input: `${tokens.radius.input}px` },
      maxWidth: { page: `${tokens.layout.webMaxWidth}px` },
      minHeight: { target: `${tokens.layout.minTarget}px` },
      minWidth: { target: `${tokens.layout.minTarget}px` },
    },
  },
  plugins: [],
} satisfies Config;
