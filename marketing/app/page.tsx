import { WaitlistForm } from "@/components/WaitlistForm";

const FEATURES = [
  {
    title: "Hybrid retrieval",
    body: "Dense vectors in Qdrant fused with keyword search, then cross-encoder reranking — so the right passage wins, not just the closest embedding.",
  },
  {
    title: "Ingest anything",
    body: "PDF, DOCX, HTML, and raw text pipelines with structure-aware chunking. Async ingestion via Celery keeps large drops off the request path.",
  },
  {
    title: "Grounded answers",
    body: "Every response cites the passages it came from. A model gateway routes across Anthropic and OpenAI with fallbacks.",
  },
  {
    title: "Quality you can gate on",
    body: "A golden-set eval harness runs in CI. Retrieval regressions fail the build before they reach production.",
  },
  {
    title: "Enterprise controls",
    body: "JWT auth with refresh tokens, API keys, per-tenant rate limits, and usage metering built in from day one.",
  },
  {
    title: "Operable by default",
    body: "Structured logs, Prometheus metrics, health probes, and a Helm chart with a ServiceMonitor — ready for your cluster.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Ingest",
    body: "Upload files or point at raw text. Documents are extracted, chunked, embedded, and indexed automatically.",
  },
  {
    n: "02",
    title: "Retrieve",
    body: "Hybrid search pulls candidates; a reranker orders them by true relevance to the question.",
  },
  {
    n: "03",
    title: "Generate",
    body: "An LLM answers strictly from retrieved context, with citations back to the source passages.",
  },
];

export default function HomePage() {
  return (
    <>
      <header className="border-b border-white/10">
        <div className="container-page flex h-16 items-center justify-between">
          <span className="text-lg font-semibold text-white">
            DClaw <span className="text-brand-500">RAG</span>
          </span>
          <a
            href="#waitlist"
            className="rounded-pill bg-brand-500 px-4 py-2 text-sm font-semibold text-ink transition hover:bg-brand-400"
          >
            Join the waitlist
          </a>
        </div>
      </header>

      <main>
        <section className="py-24 text-center">
          <div className="container-page">
            <p className="eyebrow mb-4">Universal knowledge retrieval</p>
            <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight text-white sm:text-6xl">
              Your documents,{" "}
              <span className="text-brand-500">answering questions.</span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-body sm:text-xl">
              DClaw RAG ingests any document, retrieves with hybrid search and
              reranking, and generates grounded answers with citations — as a
              platform your whole stack can call.
            </p>
            <div className="mx-auto mt-10 max-w-md">
              <WaitlistForm />
            </div>
          </div>
        </section>

        <section className="border-t border-white/10 py-20">
          <div className="container-page">
            <p className="eyebrow mb-3">How it works</p>
            <h2 className="mb-12 text-3xl font-bold text-white">
              Three steps from files to answers
            </h2>
            <div className="grid gap-8 sm:grid-cols-3">
              {STEPS.map((s) => (
                <div key={s.n}>
                  <div className="mb-3 font-mono text-sm text-brand-500">
                    {s.n}
                  </div>
                  <h3 className="mb-2 text-lg font-semibold text-white">
                    {s.title}
                  </h3>
                  <p className="text-sm leading-relaxed">{s.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-t border-white/10 py-20">
          <div className="container-page">
            <p className="eyebrow mb-3">Platform</p>
            <h2 className="mb-12 text-3xl font-bold text-white">
              Built like infrastructure, not a demo
            </h2>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map((f) => (
                <div
                  key={f.title}
                  className="rounded-xl border border-white/10 bg-white/[0.03] p-6"
                >
                  <h3 className="mb-2 font-semibold text-white">{f.title}</h3>
                  <p className="text-sm leading-relaxed">{f.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="waitlist" className="border-t border-white/10 py-24">
          <div className="container-page text-center">
            <h2 className="text-3xl font-bold text-white">
              Get early access
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-body">
              We are onboarding teams in waves. Leave your email and we will
              reach out when your slot opens.
            </p>
            <div className="mx-auto mt-8 max-w-md">
              <WaitlistForm />
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/10 py-10">
        <div className="container-page flex flex-col items-center justify-between gap-4 text-sm text-meta sm:flex-row">
          <span>© {new Date().getFullYear()} DClaw. All rights reserved.</span>
          <a
            href="https://github.com/dclawstack/dclaw-rag"
            className="transition hover:text-white"
          >
            GitHub
          </a>
        </div>
      </footer>
    </>
  );
}
