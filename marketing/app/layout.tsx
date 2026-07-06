import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DClaw RAG — Universal knowledge retrieval",
  description:
    "Ingest any document, retrieve with hybrid search and reranking, and generate grounded answers with citations. The retrieval platform behind the DClaw stack.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-sans">{children}</body>
    </html>
  );
}
