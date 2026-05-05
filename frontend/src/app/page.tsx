import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import Link from "next/link";
import { Search, FileUp, Database, Zap, ArrowRight, Sparkles } from "lucide-react";

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
            <div className="text-3xl font-bold">1</div>
            <p className="text-xs text-muted-foreground mt-1">Default collection active</p>
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
            <div className="text-3xl font-bold">0</div>
            <p className="text-xs text-muted-foreground mt-1">Ready for ingestion</p>
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

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">System Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Backend API</span>
            <Badge variant="secondary">Port 8090</Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Vector Store</span>
            <Badge variant="secondary">Qdrant</Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Embedding Model</span>
            <Badge variant="secondary">BAAI/bge-large-en-v1.5</Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">LLM Gateway</span>
            <Badge variant="secondary">OpenRouter + Kimi K2.5</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
