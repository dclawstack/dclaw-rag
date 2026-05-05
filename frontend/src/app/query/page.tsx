"use client";

import { useState } from "react";
import { queryRag, QueryResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { Search, Send, Quote, BookOpen, ChevronRight, Sparkles } from "lucide-react";

export default function QueryPage() {
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(10);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await queryRag({ question, top_k: topK });
      setResult(res);
      toast.success("Query completed", {
        description: `Retrieved ${res.retrieved_chunks.length} chunks with ${res.confidence} confidence`,
      });
    } catch (err) {
      toast.error("Query failed", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-primary" />
          Query Studio
        </h1>
        <p className="text-muted-foreground">
          Ask questions and get AI-generated answers with source citations.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6 space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="question">Question</Label>
              <div className="flex gap-2">
                <Input
                  id="question"
                  placeholder="What would you like to know?"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  className="flex-1"
                />
                <Button type="submit" disabled={loading || !question.trim()}>
                  {loading ? (
                    <Skeleton className="w-4 h-4 rounded-full" />
                  ) : (
                    <Send className="w-4 h-4 mr-2" />
                  )}
                  Ask
                </Button>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="space-y-1">
                <Label htmlFor="topk" className="text-xs">
                  Top-K: {topK}
                </Label>
                <input
                  id="topk"
                  type="range"
                  min={1}
                  max={50}
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  className="w-32 accent-primary"
                />
              </div>
              <p className="text-xs text-muted-foreground ml-auto">
                Number of chunks to retrieve
              </p>
            </div>
          </form>
        </CardContent>
      </Card>

      {loading && (
        <Card>
          <CardContent className="p-6 space-y-4">
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-4/6" />
          </CardContent>
        </Card>
      )}

      {result && !loading && (
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <Quote className="w-4 h-4 text-primary" />
                  Answer
                </CardTitle>
                <Badge
                  variant={
                    result.confidence === "high"
                      ? "default"
                      : result.confidence === "medium"
                      ? "secondary"
                      : "outline"
                  }
                >
                  {result.confidence} confidence
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap leading-relaxed">{result.answer}</p>
            </CardContent>
          </Card>

          <Tabs defaultValue="citations" className="w-full">
            <TabsList>
              <TabsTrigger value="citations" className="flex items-center gap-1">
                <Quote className="w-3 h-3" />
                Citations ({result.citations.length})
              </TabsTrigger>
              <TabsTrigger value="sources" className="flex items-center gap-1">
                <BookOpen className="w-3 h-3" />
                Sources ({result.retrieved_chunks.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="citations" className="mt-3">
              {result.citations.length === 0 ? (
                <Card>
                  <CardContent className="p-6 text-sm text-muted-foreground">
                    No citations returned.
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-2">
                  {result.citations.map((citation) => (
                    <Card key={citation.index}>
                      <CardContent className="p-4 flex items-start gap-3">
                        <Badge variant="outline" className="shrink-0 mt-0.5">
                          #{citation.index}
                        </Badge>
                        <div className="space-y-1 min-w-0">
                          <p className="text-sm font-medium truncate">
                            {citation.source}
                          </p>
                          <p className="text-xs text-muted-foreground font-mono truncate">
                            {citation.chunk_id}
                          </p>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="sources" className="mt-3">
              <ScrollArea className="h-[500px]">
                <div className="space-y-3 pr-4">
                  {result.retrieved_chunks.map((chunk, idx) => (
                    <Card key={chunk.id}>
                      <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-xs font-medium flex items-center gap-2">
                            <ChevronRight className="w-3 h-3 text-primary" />
                            Chunk {idx + 1}
                            <Badge variant="secondary" className="text-xs">
                              Score: {chunk.score.toFixed(3)}
                            </Badge>
                          </CardTitle>
                          <span className="text-xs text-muted-foreground font-mono truncate max-w-[200px]">
                            {chunk.id}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Source: {chunk.metadata.source}
                          {chunk.metadata.title && ` • ${chunk.metadata.title}`}
                        </p>
                      </CardHeader>
                      <Separator />
                      <CardContent className="pt-3">
                        <p className="text-sm leading-relaxed">{chunk.text}</p>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </ScrollArea>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
}
