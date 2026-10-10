import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aura Skincare | Talk to Aria",
  description: "Browser voice support for Aura Skincare orders and policies.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}

