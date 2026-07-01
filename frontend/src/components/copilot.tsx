"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { queryRag } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sparkles,
  X,
  Send,
  Quote,
  FileUp,
  Search,
  Database,
} from "lucide-react";
import { GroundingBadge } from "@/components/grounding-badge";

interface Citation {
  index: number;
  source: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  confidence?: "high" | "medium" | "low";
  citations?: Citation[];
  abstained?: boolean;
  faithfulness?: "grounded" | "partial" | "unsupported" | null;
}

const EXAMPLE_PROMPTS = [
  "What topics are covered in my knowledge base?",
  "Summarize the most important points.",
];

const QUICK_ACTIONS = [
  { href: "/ingest", label: "Upload docs", icon: FileUp },
  { href: "/query", label: "Query Studio", icon: Search },
  { href: "/collections", label: "Collections", icon: Database },
];

export function Copilot() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: q }]);
    setLoading(true);
    try {
      const res = await queryRag({ question: q, top_k: 5 });
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: res.answer,
          confidence: res.confidence,
          citations: res.citations?.map((c) => ({ index: c.index, source: c.source })),
          abstained: res.abstained,
          faithfulness: res.faithfulness,
        },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content:
            "I couldn't reach the knowledge base. Make sure documents are ingested and the backend is running.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  if (!open) {
    return (
      <button
        aria-label="Open AI copilot"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform hover:scale-105"
      >
        <Sparkles className="h-6 w-6" />
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex h-[560px] w-[400px] max-w-[calc(100vw-3rem)] flex-col rounded-xl border bg-card shadow-2xl">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2 font-semibold">
          <Sparkles className="h-5 w-5 text-primary" />
          Knowledge Copilot
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          aria-label="Close copilot"
          onClick={() => setOpen(false)}
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="space-y-4 p-4">
          {messages.length === 0 && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Ask anything about your knowledge base — I&apos;ll answer with cited sources.
              </p>
              <div className="space-y-2">
                {EXAMPLE_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => ask(prompt)}
                    className="block w-full rounded-md border bg-background px-3 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={msg.role === "user" ? "flex justify-end" : "flex justify-start"}
            >
              <div
                className={
                  msg.role === "user"
                    ? "max-w-[85%] rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground"
                    : "max-w-[90%] space-y-2 rounded-lg bg-muted px-3 py-2 text-sm"
                }
              >
                <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                {msg.role === "assistant" && msg.confidence && (
                  <div className="flex flex-wrap items-center gap-1 pt-1">
                    <GroundingBadge abstained={msg.abstained} faithfulness={msg.faithfulness} />
                    <Badge variant="outline" className="text-[10px]">
                      {msg.confidence} confidence
                    </Badge>
                    {msg.citations?.map((c) => (
                      <Badge key={c.index} variant="secondary" className="gap-1 text-[10px]">
                        <Quote className="h-2.5 w-2.5" />
                        {c.source}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
                Searching the knowledge base…
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </ScrollArea>

      <div className="border-t p-3">
        <div className="mb-2 flex flex-wrap gap-1">
          {QUICK_ACTIONS.map((action) => {
            const Icon = action.icon;
            return (
              <Link
                key={action.href}
                href={action.href}
                onClick={() => setOpen(false)}
                className="inline-flex items-center gap-1 rounded-full border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                <Icon className="h-3 w-3" />
                {action.label}
              </Link>
            );
          })}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(input);
          }}
          className="flex gap-2"
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask your knowledge base…"
            disabled={loading}
          />
          <Button
            type="submit"
            size="icon"
            aria-label="Send message"
            disabled={loading || !input.trim()}
          >
            <Send className="h-4 w-4" aria-hidden="true" />
          </Button>
        </form>
      </div>
    </div>
  );
}
