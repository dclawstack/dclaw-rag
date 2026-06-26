"use client";

import { useEffect, useState } from "react";
import { getStats, Stats } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { Database, FileUp, Zap, ArrowRight } from "lucide-react";

export function DashboardStats() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch(() => setStats(null));
  }, []);

  const num = (n: number | undefined) => (n === undefined ? "—" : String(n));

  return (
    <div className="grid gap-4 md:grid-cols-3">
      <Card className="relative overflow-hidden">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Database className="w-4 h-4 text-primary" />
            Collections
          </CardTitle>
          <CardDescription>Organize documents into collections</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold">{num(stats?.collections)}</div>
          <p className="text-xs text-muted-foreground mt-1">Active collections</p>
          <Link href="/collections">
            <Button size="sm" className="mt-4 w-full">
              Manage <ArrowRight className="w-3 h-3 ml-1" />
            </Button>
          </Link>
        </CardContent>
      </Card>

      <Card className="relative overflow-hidden">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <FileUp className="w-4 h-4 text-primary" />
            Documents
          </CardTitle>
          <CardDescription>Ingest files and raw text</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold">{num(stats?.documents)}</div>
          <p className="text-xs text-muted-foreground mt-1">
            {stats ? `${stats.chunks} chunks indexed` : "In the knowledge base"}
          </p>
          <Link href="/ingest">
            <Button size="sm" className="mt-4 w-full">
              Upload <ArrowRight className="w-3 h-3 ml-1" />
            </Button>
          </Link>
        </CardContent>
      </Card>

      <Card className="relative overflow-hidden">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Zap className="w-4 h-4 text-primary" />
            Queries
          </CardTitle>
          <CardDescription>Ask questions of your data</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold">—</div>
          <p className="text-xs text-muted-foreground mt-1">Query studio ready</p>
          <Link href="/query">
            <Button size="sm" className="mt-4 w-full">
              Query <ArrowRight className="w-3 h-3 ml-1" />
            </Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
