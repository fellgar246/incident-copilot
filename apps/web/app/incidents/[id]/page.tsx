import { IncidentDetail } from "@/components/incident-detail";

export function generateStaticParams() {
  return [{ id: "_" }];
}

export default function IncidentPage() {
  return <IncidentDetail />;
}
