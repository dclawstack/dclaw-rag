"use client";

import { useState, useEffect } from "react";
import {
  queryRag,
  agentQuery,
  QueryResponse,
  AgentResponse,
  AgentStep,
  listCollections,
  Collection,
} from "@/lib/api";
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
import { Send, Quote, BookOpen, ChevronRight, Sparkles, ListTree } from "lucide-react";
import { GroundingBadge } from "@/components/grounding-badge";

export default function QueryPage() {
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(10);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResponse | AgentResponse | null>(null);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [agentic, setAgentic] = useState(false);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [collectionId, setCollectionId] = useState("");

  useEffect(() => {
    listCollections()
      .then(setCollections)
      .catch(() => setCollections([]));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setResult(null);
    setSteps([]);
    try {
      if (agentic) {
        const res = await agentQuery({
          question,
          top_k: topK,
          collection_id: collectionId || undefined,
        });
        setResult(res);
        setSteps(res.steps);
        toast.success("Agentic query completed", {
          description: `${res.steps.length} reasoning steps · ${res.confidence} confidence`,
        });
      } else {
        const res = await queryRag({
          question,
          top_k: topK,
          collection_id: collectionId || undefined,
        });
        setResult(res);
        toast.success("Query completed", {
          description: `Retrieved ${res.retrieved_chunks.length} chunks with ${res.confidence} confidence`,
        });
      }
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
                <Label htmlFor="query-collection" className="text-xs">
                  Collection
                </Label>
                <select
                  id="query-collection"
                  value={collectionId}
                  onChange={(e) => setCollectionId(e.target.value)}
                  className="flex h-8 rounded-md border border-input bg-transparent px-2 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="">All collections</option>
                  {collections.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
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
              <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer ml-auto">
                <input
                  type="checkbox"
                  checked={agentic}
                  onChange={(e) => setAgentic(e.target.checked)}
                  className="accent-primary"
                />
                Agentic (multi-step)
              </label>
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

      {!result && !loading && (
        <Card>
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            Ask a question above to get an answer with cited sources from your
            knowledge base.
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
                <div className="flex items-center gap-2">
                  <GroundingBadge
                    abstained={(result as QueryResponse).abstained}
                    faithfulness={(result as QueryResponse).faithfulness}
                  />
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
              </div>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap leading-relaxed">{result.answer}</p>
              {(result as QueryResponse).unsupported_claims &&
                (result as QueryResponse).unsupported_claims!.length > 0 && (
                  <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs">
                    <p className="mb-1 font-medium text-amber-800">
                      Claims not verified against the sources:
                    </p>
                    <ul className="list-disc space-y-1 pl-4 text-amber-700">
                      {(result as QueryResponse).unsupported_claims!.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
            </CardContent>
          </Card>

          {steps.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <ListTree className="w-4 h-4 text-primary" />
                  Reasoning chain ({steps.length} {steps.length === 1 ? "step" : "steps"})
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {steps.map((step, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-sm">
                    <Badge variant="outline" className="shrink-0 mt-0.5">
                      {idx + 1}
                    </Badge>
                    <span className="flex-1">{step.sub_question}</span>
                    <Badge variant="secondary" className="shrink-0">
                      {step.n_results} hits
                    </Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

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
