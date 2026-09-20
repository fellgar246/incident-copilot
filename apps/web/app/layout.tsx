import type { ReactNode } from "react";

export const metadata = {
  title: "AI Incident Copilot",
  description: "Detect, investigate, and remediate incidents with a governed agent.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
