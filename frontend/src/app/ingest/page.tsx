"use client";

import { useState, useCallback, useEffect } from "react";
import { ingestFile, ingestText, listCollections, Collection } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { FileUp, Type, Upload, CheckCircle, AlertCircle, X } from "lucide-react";

export default function IngestPage() {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [source, setSource] = useState("user-upload");
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [collectionId, setCollectionId] = useState("");

  useEffect(() => {
    listCollections()
      .then(setCollections)
      .catch(() => setCollections([]));
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const dropped = e.dataTransfer.files[0];
      if (dropped) {
        setFile(dropped);
        if (!title) setTitle(dropped.name);
      }
    },
    [title]
  );

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      setFile(selected);
      if (!title) setTitle(selected.name);
    }
  };

  async function submitFile() {
    if (!file) return;
    setLoading(true);
    setProgress(30);
    try {
      const res = await ingestFile(file, {
        source,
        title: title || file.name,
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
        collection_id: collectionId || undefined,
      });
      setProgress(100);
      toast.success("Document queued", {
        description: `Document ${res.doc_id} is ${res.status} — processing in the background`,
      });
      setFile(null);
      setTitle("");
      setTags("");
    } catch (err) {
      toast.error("Ingestion failed", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    } finally {
      setLoading(false);
      setProgress(0);
    }
  }

  async function submitText() {
    if (!text.trim()) return;
    setLoading(true);
    setProgress(30);
    try {
      const res = await ingestText(text, {
        source,
        title: title || "Text ingestion",
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
        collection_id: collectionId || undefined,
      });
      setProgress(100);
      toast.success("Document queued", {
        description: `Document ${res.doc_id} is ${res.status} — processing in the background`,
      });
      setText("");
      setTitle("");
      setTags("");
    } catch (err) {
      toast.error("Ingestion failed", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    } finally {
      setLoading(false);
      setProgress(0);
    }
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <FileUp className="w-6 h-6 text-primary" />
          Upload & Ingest
        </h1>
        <p className="text-muted-foreground">
          Add documents to your knowledge base via file upload or raw text.
        </p>
      </div>

      <Tabs defaultValue="file" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="file" className="flex items-center gap-1">
            <Upload className="w-3 h-3" />
            File Upload
          </TabsTrigger>
          <TabsTrigger value="text" className="flex items-center gap-1">
            <Type className="w-3 h-3" />
            Raw Text
          </TabsTrigger>
        </TabsList>

        <TabsContent value="file" className="mt-4 space-y-4">
          <Card>
            <CardContent className="pt-6 space-y-4">
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                  dragOver
                    ? "border-primary bg-primary/5"
                    : "border-muted-foreground/25 hover:border-muted-foreground/50"
                }`}
              >
                {file ? (
                  <div className="flex items-center justify-center gap-3">
                    <CheckCircle className="w-5 h-5 text-emerald-500" />
                    <span className="text-sm font-medium">{file.name}</span>
                    <Badge variant="secondary">{(file.size / 1024).toFixed(1)} KB</Badge>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6"
                      onClick={() => setFile(null)}
                    >
                      <X className="w-3 h-3" />
                    </Button>
                  </div>
                ) : (
                  <label className="cursor-pointer block">
                    <Upload className="w-8 h-8 mx-auto text-muted-foreground mb-2" />
                    <p className="text-sm font-medium">
                      Drag & drop a file here, or click to browse
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Supports PDF, Word, Markdown, HTML, CSV, and text files
                    </p>
                    <input
                      type="file"
                      className="hidden"
                      onChange={handleFileInput}
                      accept=".pdf,.docx,.md,.markdown,.txt,.html,.htm,.csv,.tsv,.json,.yaml,.yml,.rst,.log,.text"
                    />
                  </label>
                )}
              </div>

              <div className="grid gap-3">
                <div className="space-y-1">
                  <Label htmlFor="file-collection">Collection</Label>
                  <select
                    id="file-collection"
                    value={collectionId}
                    onChange={(e) => setCollectionId(e.target.value)}
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <option value="">No collection</option>
                    {collections.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="file-source">Source</Label>
                  <Input
                    id="file-source"
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                    placeholder="e.g. user-upload, slack, confluence"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="file-title">Title (optional)</Label>
                  <Input
                    id="file-title"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Document title"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="file-tags">Tags (comma separated)</Label>
                  <Input
                    id="file-tags"
                    value={tags}
                    onChange={(e) => setTags(e.target.value)}
                    placeholder="legal, hr, onboarding"
                  />
                </div>
              </div>

              {loading && <Progress value={progress} className="w-full" />}

              <Button
                onClick={submitFile}
                disabled={!file || loading}
                className="w-full"
              >
                <Upload className="w-4 h-4 mr-2" />
                {loading ? "Ingesting..." : "Ingest File"}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="text" className="mt-4 space-y-4">
          <Card>
            <CardContent className="pt-6 space-y-4">
              <div className="space-y-1">
                <Label htmlFor="text-content">Content</Label>
                <Textarea
                  id="text-content"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Paste your text here..."
                  rows={10}
                />
              </div>

              <div className="grid gap-3">
                <div className="space-y-1">
                  <Label htmlFor="text-collection">Collection</Label>
                  <select
                    id="text-collection"
                    value={collectionId}
                    onChange={(e) => setCollectionId(e.target.value)}
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <option value="">No collection</option>
                    {collections.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="text-source">Source</Label>
                  <Input
                    id="text-source"
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                    placeholder="e.g. user-upload, slack, confluence"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="text-title">Title (optional)</Label>
                  <Input
                    id="text-title"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Document title"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="text-tags">Tags (comma separated)</Label>
                  <Input
                    id="text-tags"
                    value={tags}
                    onChange={(e) => setTags(e.target.value)}
                    placeholder="legal, hr, onboarding"
                  />
                </div>
              </div>

              {loading && <Progress value={progress} className="w-full" />}

              <Button
                onClick={submitText}
                disabled={!text.trim() || loading}
                className="w-full"
              >
                <Type className="w-4 h-4 mr-2" />
                {loading ? "Ingesting..." : "Ingest Text"}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Card className="bg-amber-50 border-amber-200">
        <CardContent className="p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-sm text-amber-900 space-y-1">
            <p className="font-medium">Ingestion Pipeline</p>
            <p className="text-amber-800/80">
              Documents are extracted, chunked, embedded, and stored in Qdrant.
              Large files may take a moment to process.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
