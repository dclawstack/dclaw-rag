import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { DashboardStats } from "@/components/dashboard-stats";
import { SystemStatus } from "@/components/system-status";
import Link from "next/link";
import { Search, FileUp, Database, Sparkles } from "lucide-react";

export default function DashboardPage() {
  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-primary" />
          DClaw RAG
        </h1>
        <p className="text-muted-foreground">
          Universal knowledge retrieval — ingest documents, query your knowledge base, and get
          AI-powered answers with citations.
        </p>
      </div>

      <DashboardStats />

      <Separator />

      <div className="space-y-3">
        <h2 className="text-lg font-semibold">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          <Link href="/query">
            <Button>
              <Search className="w-4 h-4 mr-2" />
              Open Query Studio
            </Button>
          </Link>
          <Link href="/ingest">
            <Button variant="outline">
              <FileUp className="w-4 h-4 mr-2" />
              Upload Documents
            </Button>
          </Link>
          <Link href="/collections">
            <Button variant="outline">
              <Database className="w-4 h-4 mr-2" />
              Manage Collections
            </Button>
          </Link>
        </div>
      </div>

      <SystemStatus />
    </div>
  );
}
