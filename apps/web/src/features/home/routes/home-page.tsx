import {
  ArrowRight,
  Boxes,
  Database,
  FileSearch,
  MapPinned,
  Radar,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuthSession } from "@/features/auth/session";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { productName, repositorySlug } from "@/lib/brand";
import { appPaths } from "@/app/paths";
import heroScene from "@/assets/marketing/leadscope-hero-scene.png";
import evidenceScene from "@/assets/marketing/leadscope-evidence-scene.png";
import workflowScene from "@/assets/marketing/leadscope-workflow-scene.png";

const operatingSignals = [
  {
    label: "Provider coverage",
    value: "Maps search, place enrichment, and web visibility checks from one acquisition layer.",
  },
  {
    label: "Lead truth model",
    value: "Raw payloads, normalized facts, scores, and AI outputs stay separated and auditable.",
  },
  {
    label: "Agency action loop",
    value: "Search, qualify, assign, explain, recommend services, and draft outreach in one desk.",
  },
  {
    label: "Release posture",
    value: "FastAPI + React monorepo with GHCR image publishing and deploy-ready compose wiring.",
  },
];

const pillars = [
  {
    title: "Evidence archive first",
    description:
      "Every provider round stores request metadata, immutable raw payloads, and queryable normalized facts before anything is scored or drafted.",
    icon: Database,
  },
  {
    title: "Deterministic qualification",
    description:
      "Lead scores come from reproducible rules over normalized SerpAPI evidence, with persisted breakdowns and versioned scoring configs.",
    icon: Radar,
  },
  {
    title: "AI stays assistive",
    description:
      "Recommendations and outreach drafts sit on top of stored facts and score context. They never overwrite lead truth data.",
    icon: ShieldCheck,
  },
];

const workflowSteps = [
  {
    step: "01",
    title: "Search by category and city",
    description:
      "Agencies launch scoped discovery runs with thresholds for rating, reviews, radius, website presence, and keyword intent.",
  },
  {
    step: "02",
    title: "Normalize and deduplicate",
    description:
      "Maps search, place detail, and web search results are converted into internal fact records, linked to source evidence, and merged deterministically.",
  },
  {
    step: "03",
    title: "Score and qualify",
    description:
      "The engine evaluates local trust, website strength, visibility, opportunity, and confidence to produce reproducible qualification bands.",
  },
  {
    step: "04",
    title: "Recommend and draft",
    description:
      "Only after the evidence stack is stable does the assistive layer generate weaknesses, service recommendations, and editable outreach drafts.",
  },
];

const capabilities = [
  "SerpAPI-driven local discovery",
  "Lead map and table synchronization",
  "Dedup by place, domain, phone, and name fallback",
  "Versioned scoring configuration",
  "Persisted AI snapshots and outreach versions",
  "Admin controls, audit logs, and CSV export",
];

export function HomePage() {
  useDocumentTitle("LeadScope AI");
  const { isAuthenticated } = useAuthSession();
  const workspacePath = appPaths.dashboard;
  const entryPath = isAuthenticated ? workspacePath : appPaths.login;

  return (
    <div className="home-page relative overflow-x-clip text-[color:var(--text)]">
      <div className="home-page__aurora pointer-events-none absolute inset-x-0 top-0 h-[52rem]" />

      <header className="sticky top-0 z-40 border-b border-white/45 bg-[rgba(244,248,244,0.78)] backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-[1240px] items-center justify-between gap-6 px-4 py-4 lg:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#073b3a_0%,#0f766e_100%)] text-sm font-extrabold text-white shadow-[0_18px_34px_-22px_rgba(15,118,110,0.8)]">
              LS
            </div>
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.26em] text-[color:var(--muted)]">
                {productName}
              </p>
              <p className="text-sm font-semibold">Smart lead finder for agencies</p>
            </div>
          </div>

          <nav className="hidden items-center gap-6 text-sm font-semibold text-[color:var(--muted)] lg:flex">
            <a href="#workflow" className="transition hover:text-[color:var(--text)]">
              Workflow
            </a>
            <a href="#evidence" className="transition hover:text-[color:var(--text)]">
              Evidence
            </a>
            <a href="#stack" className="transition hover:text-[color:var(--text)]">
              Stack
            </a>
            <a href="#cta" className="transition hover:text-[color:var(--text)]">
              Access
            </a>
          </nav>

          <div className="flex items-center gap-3">
            <Button asChild variant="ghost" className="hidden sm:inline-flex">
              <Link to={appPaths.login}>Sign in</Link>
            </Button>
            <Button asChild>
              <Link to={entryPath}>
                {isAuthenticated ? "Open workspace" : "Enter workspace"}
                <ArrowRight className="ms-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </header>

      <main>
        <section className="relative px-4 pb-10 pt-12 lg:px-6 lg:pb-16 lg:pt-14">
          <div className="mx-auto grid w-full max-w-[1240px] gap-10 lg:grid-cols-[minmax(0,0.96fr)_minmax(0,1.04fr)] lg:items-center">
            <div className="space-y-8">
              <div className="inline-flex items-center gap-2 rounded-full border border-[rgba(15,118,110,0.16)] bg-white/80 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--accent-ink)] shadow-[0_16px_30px_-26px_rgba(15,118,110,0.65)]">
                <Sparkles className="h-3.5 w-3.5" />
                Deterministic lead qualification for modern agencies
              </div>

              <div className="space-y-5">
                <h1 className="max-w-3xl text-5xl font-extrabold leading-[1.02] tracking-[-0.04em] text-[color:var(--text)] sm:text-6xl lg:text-[4.6rem]">
                  Turn local search evidence into qualified outreach you can defend.
                </h1>
                <p className="max-w-2xl text-lg leading-8 text-[color:var(--muted)]">
                  LeadScope AI helps agencies move from category-plus-city discovery to scored,
                  explainable, service-ready leads. SerpAPI data is archived, normalized,
                  deduplicated, scored, and only then passed to an assistive draft layer.
                </p>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row">
                <Button asChild className="justify-center sm:min-w-[190px]">
                  <Link to={entryPath}>
                    {isAuthenticated ? "Open the desk" : "Sign in to workspace"}
                    <ArrowRight className="ms-2 h-4 w-4" />
                  </Link>
                </Button>
                <Button asChild variant="secondary" className="justify-center sm:min-w-[190px]">
                  <a href="#workflow">See the operating flow</a>
                </Button>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <SignalCard
                  title="Evidence first"
                  description="Raw payloads, normalized facts, and lead-source links stay auditable."
                  icon={FileSearch}
                />
                <SignalCard
                  title="Maps-native desk"
                  description="Leaflet views stay synchronized with filters, selected lead, and search geography."
                  icon={MapPinned}
                />
                <SignalCard
                  title="Service-ready output"
                  description="Qualification, recommendations, and outreach drafts stay tied to stored proof."
                  icon={Boxes}
                />
              </div>
            </div>

            <div className="home-scene relative">
              <div className="home-scene__glow home-scene__glow--teal" />
              <div className="home-scene__glow home-scene__glow--amber" />
              <div className="home-scene__frame">
                <div className="home-scene__mesh" />
                <img
                  src={heroScene}
                  alt="LeadScope AI hero illustration showing layered 3D analytics panels and mapped lead markers."
                  className="home-scene__image"
                />
                <div className="home-floating-card home-floating-card--top">
                  <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-teal-100/72">
                    Acquisition layer
                  </p>
                  <p className="mt-2 text-lg font-bold text-white">Maps search, place detail, web validation</p>
                  <p className="mt-2 text-sm leading-6 text-teal-50/78">
                    One provider surface, normalized into internal facts before the lead desk touches it.
                  </p>
                </div>
                <div className="home-floating-card home-floating-card--bottom">
                  <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-amber-100/72">
                    Qualification engine
                  </p>
                  <p className="mt-2 text-lg font-bold text-white">Versioned scoring with explainable bands</p>
                  <p className="mt-2 text-sm leading-6 text-white/76">
                    Local trust, website signal, search visibility, opportunity, and data confidence in one reproducible score.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="px-4 py-8 lg:px-6">
          <div className="mx-auto grid w-full max-w-[1240px] gap-4 md:grid-cols-2 xl:grid-cols-4">
            {operatingSignals.map((signal) => (
              <div
                key={signal.label}
                className="rounded-[1.6rem] border border-[rgba(24,34,29,0.08)] bg-white/82 p-5 shadow-[0_25px_44px_-34px_rgba(15,23,42,0.34)] backdrop-blur"
              >
                <p className="font-mono text-xs uppercase tracking-[0.2em] text-[color:var(--muted)]">
                  {signal.label}
                </p>
                <p className="mt-3 text-sm leading-7 text-[color:var(--text)]">{signal.value}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="evidence" className="px-4 py-14 lg:px-6 lg:py-20">
          <div className="mx-auto grid w-full max-w-[1240px] gap-8 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)] lg:items-center">
            <div className="space-y-6">
              <SectionIntro
                eyebrow="Evidence architecture"
                title="The home page says exactly what the product does under the hood."
                description="This is not a cosmetic layer over loose scraping. The product stores provider fetches, immutable raw payloads, normalized fact rows, lead-source linkage, score breakdowns, and assistive snapshots as distinct records."
              />

              <div className="grid gap-4">
                {pillars.map((pillar) => (
                  <div
                    key={pillar.title}
                    className="rounded-[1.6rem] border border-[rgba(24,34,29,0.09)] bg-[rgba(255,255,255,0.84)] p-5 shadow-[0_24px_40px_-34px_rgba(15,23,42,0.3)]"
                  >
                    <div className="flex items-start gap-4">
                      <div className="mt-1 flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,var(--accent)_0%,#0d9488_100%)] text-white">
                        <pillar.icon className="h-5 w-5" />
                      </div>
                      <div>
                        <h2 className="text-lg font-bold">{pillar.title}</h2>
                        <p className="mt-2 text-sm leading-7 text-[color:var(--muted)]">
                          {pillar.description}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="relative">
              <div className="home-gallery-card">
                <img
                  src={evidenceScene}
                  alt="Generated evidence scene showing stacked glass panels that represent stored provider records and normalized facts."
                  className="home-gallery-card__image"
                />
              </div>
            </div>
          </div>
        </section>

        <section id="workflow" className="px-4 py-14 lg:px-6 lg:py-20">
          <div className="mx-auto w-full max-w-[1240px] space-y-8">
            <SectionIntro
              eyebrow="Operating flow"
              title="From local discovery to agency handoff without collapsing evidence boundaries."
              description="The product flow stays intentionally opinionated: acquire data, normalize it, deduplicate deterministically, score it with versioned rules, and only then generate assistive output."
            />

            <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
              <div className="grid gap-4 md:grid-cols-2">
                {workflowSteps.map((step) => (
                  <div
                    key={step.step}
                    className="rounded-[1.7rem] border border-[rgba(24,34,29,0.08)] bg-white/84 p-5 shadow-[0_24px_44px_-34px_rgba(15,23,42,0.32)]"
                  >
                    <p className="font-mono text-xs uppercase tracking-[0.24em] text-[color:var(--accent)]">
                      {step.step}
                    </p>
                    <h3 className="mt-3 text-lg font-bold">{step.title}</h3>
                    <p className="mt-3 text-sm leading-7 text-[color:var(--muted)]">{step.description}</p>
                  </div>
                ))}
              </div>

              <div className="home-gallery-card home-gallery-card--dark">
                <img
                  src={workflowScene}
                  alt="Generated workflow illustration showing connected lead-processing stages across a stylized 3D plane."
                  className="home-gallery-card__image"
                />
              </div>
            </div>
          </div>
        </section>

        <section id="stack" className="px-4 py-14 lg:px-6 lg:py-20">
          <div className="mx-auto grid w-full max-w-[1240px] gap-8 xl:grid-cols-[0.96fr_1.04fr]">
            <div className="rounded-[2rem] border border-[rgba(24,34,29,0.08)] bg-[linear-gradient(180deg,rgba(255,255,255,0.88)_0%,rgba(245,249,246,0.92)_100%)] p-6 shadow-[0_30px_60px_-40px_rgba(15,23,42,0.35)] lg:p-8">
              <SectionIntro
                eyebrow="Deployment posture"
                title="Built to survive real delivery, not just a one-screen demo."
                description="The repo already ships with quality gates, container packaging, published images, and manual deploy wiring. The homepage matches that posture instead of pretending the app is a generic template."
              />

              <div className="mt-8 grid gap-3">
                {capabilities.map((capability) => (
                  <div
                    key={capability}
                    className="flex items-center gap-3 rounded-2xl border border-[rgba(24,34,29,0.08)] bg-white/72 px-4 py-3 text-sm font-semibold text-[color:var(--text)]"
                  >
                    <span className="h-2.5 w-2.5 rounded-full bg-[color:var(--accent)]" />
                    {capability}
                  </div>
                ))}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <StackCard
                title="Backend"
                description="FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, HTTPX, MariaDB-ready."
              />
              <StackCard
                title="Frontend"
                description="React, Vite, TypeScript strict mode, Tailwind, TanStack Query, React Hook Form, React Leaflet."
              />
              <StackCard
                title="Governance"
                description="Audit logs, provider settings, prompt templates, score versions, health and recent failures."
              />
              <StackCard
                title="Delivery"
                description={`${repositorySlug} monorepo, GitHub Actions CI/CD, GHCR image publishing, deploy compose.`}
              />
            </div>
          </div>
        </section>

        <section id="cta" className="px-4 pb-20 pt-8 lg:px-6">
          <div className="mx-auto w-full max-w-[1240px]">
            <div className="home-cta-panel overflow-hidden rounded-[2.25rem] p-7 lg:p-10">
              <div className="relative z-10 flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
                <div className="max-w-2xl">
                  <p className="font-mono text-xs uppercase tracking-[0.24em] text-teal-100/72">
                    Workspace access
                  </p>
                  <h2 className="mt-3 text-3xl font-extrabold text-white sm:text-4xl">
                    Open the lead desk and move from discovery to qualification in one pass.
                  </h2>
                  <p className="mt-4 text-sm leading-7 text-white/74">
                    Use the authenticated workspace for search jobs, lead maps, score explanations,
                    admin controls, and editable outreach drafts. The homepage is public; the desk
                    is where the work happens.
                  </p>
                </div>

                <div className="flex flex-col gap-3 sm:flex-row">
                  <Button asChild className="justify-center bg-white text-[#0b2a27] hover:bg-[#e9faf6]">
                    <Link to={entryPath}>
                      {isAuthenticated ? "Enter workspace" : "Sign in now"}
                      <ArrowRight className="ms-2 h-4 w-4" />
                    </Link>
                  </Button>
                  <Button
                    asChild
                    variant="secondary"
                    className="justify-center border-white/18 bg-white/10 text-white hover:bg-white/16"
                  >
                    <a href="#evidence">Review the evidence model</a>
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

function SectionIntro({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div>
      <p className="font-mono text-xs uppercase tracking-[0.24em] text-[color:var(--accent)]">
        {eyebrow}
      </p>
      <h2 className="mt-3 text-3xl font-extrabold tracking-[-0.03em] sm:text-[2.35rem]">{title}</h2>
      <p className="mt-4 max-w-3xl text-sm leading-8 text-[color:var(--muted)]">{description}</p>
    </div>
  );
}

function SignalCard({
  title,
  description,
  icon: Icon,
}: {
  title: string;
  description: string;
  icon: typeof FileSearch;
}) {
  return (
    <div className="rounded-[1.55rem] border border-[rgba(24,34,29,0.08)] bg-white/82 p-4 shadow-[0_20px_34px_-30px_rgba(15,23,42,0.28)] backdrop-blur">
      <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[color:var(--accent-soft)] text-[color:var(--accent)]">
        <Icon className="h-5 w-5" />
      </div>
      <p className="mt-4 text-sm font-bold">{title}</p>
      <p className="mt-2 text-sm leading-7 text-[color:var(--muted)]">{description}</p>
    </div>
  );
}

function StackCard({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-[1.75rem] border border-[rgba(24,34,29,0.08)] bg-white/84 p-5 shadow-[0_24px_44px_-34px_rgba(15,23,42,0.3)]">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-[color:var(--muted)]">{title}</p>
      <p className="mt-3 text-sm leading-7 text-[color:var(--text)]">{description}</p>
    </div>
  );
}

