"use client";

import Link from "next/link";
import { APP_COLOR } from "@/lib/tokens";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useEffect, useState } from "react";
import { healthCheck } from "@/lib/api";
import { Circle, GitBranch } from "lucide-react";

export function Navbar() {
  const [status, setStatus] = useState<"online" | "offline" | "loading">("loading");
  const [version, setVersion] = useState("");

  useEffect(() => {
    healthCheck()
      .then((res) => {
        setStatus(res.status === "ok" ? "online" : "offline");
        setVersion(res.version || "");
      })
      .catch(() => setStatus("offline"));
  }, []);

  return (
    <header className="h-14 border-b bg-card flex items-center justify-between px-4 shrink-0">
      <div className="flex items-center gap-3">
        <Badge
          variant="outline"
          className="gap-1.5 text-xs font-normal"
        >
          <Circle
            className={`w-2 h-2 fill-current ${
              status === "online"
                ? "text-emerald-500"
                : status === "offline"
                ? "text-red-500"
                : "text-amber-500"
            }`}
          />
          API {status}
          {version && <span className="text-muted-foreground">v{version}</span>}
        </Badge>
      </div>
      <div className="flex items-center gap-3">
        <span
          className="text-xs font-medium px-2 py-0.5 rounded-full text-white"
          style={{ backgroundColor: APP_COLOR }}
        >
          P0
        </span>
        <Link href="https://github.com/dclawstack/dclaw-rag" target="_blank" rel="noopener noreferrer">
          <Button variant="ghost" size="sm">
            <GitBranch className="w-4 h-4 mr-1" />
            Repo
          </Button>
        </Link>
      </div>
    </header>
  );
}
