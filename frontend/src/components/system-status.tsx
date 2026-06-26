"use client";

import { useEffect, useState } from "react";
import { getSystemInfo, SystemInfo } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

function cap(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function SystemStatus() {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getSystemInfo()
      .then(setInfo)
      .catch(() => setError(true));
  }, []);

  const rows: [string, string][] = info
    ? [
        ["Backend API", `Port ${info.backend_port}`],
        ["Vector Store", info.vector_store],
        ["Embedding Model", info.embedding_model],
        ["Reranker", info.reranker_model],
        ["LLM Gateway", `${cap(info.llm_provider)} · ${info.llm_model}`],
      ]
    : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">System Status</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {error && <p className="text-muted-foreground">Backend unavailable</p>}
        {!info && !error && <p className="text-muted-foreground">Loading…</p>}
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between">
            <span className="text-muted-foreground">{label}</span>
            <Badge variant="secondary">{value}</Badge>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
