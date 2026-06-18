import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "DataChat",
  description: "Upload CSVs and ask questions in natural language.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="h-full">{children}</body>
    </html>
  );
}
