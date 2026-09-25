"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/incidents", label: "Incidents" },
  { href: "/evaluations", label: "Evaluations" },
  { href: "/settings/costs", label: "Settings / Costs" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "";
  return (
    <div className="app-shell">
      <nav className="nav" aria-label="Primary">
        <div className="brand">
          <strong>AI Incident Copilot</strong>
          <span>Governed investigation</span>
        </div>
        {LINKS.map((link) => {
          const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
          return (
            <a key={link.href} href={link.href} data-active={active}>
              {link.label}
            </a>
          );
        })}
      </nav>
      <div className="content">{children}</div>
    </div>
  );
}
