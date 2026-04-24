import { motion } from "framer-motion";
import { LeadScopeWordmark } from "@/components/brand/logo";
import { ShieldCheck, Radar, Network, Lock } from "lucide-react";

const PROOF_POINTS = [
  {
    icon: Radar,
    title: "Evidence-backed lead intelligence",
    body: "Every score traces to normalized provider facts — no hallucinated signals.",
  },
  {
    icon: Network,
    title: "Deterministic scoring pipeline",
    body: "Versioned weights, reproducible stages, full audit visibility.",
  },
  {
    icon: ShieldCheck,
    title: "Operator-grade governance",
    body: "Role-aware access, exports with retention, immutable event log.",
  },
];

export function AuthSidebar() {
  return (
    <aside className="relative hidden flex-col justify-between overflow-hidden border-r border-border bg-[oklch(0.15_0.01_240)] p-10 lg:flex">
      <div className="pointer-events-none absolute inset-0 bg-grid bg-grid-fade opacity-40" />
      <div
        className="pointer-events-none absolute -right-24 top-1/3 size-[420px] rounded-full blur-3xl"
        style={{ background: "radial-gradient(circle, oklch(0.82 0.14 195 / 0.18), transparent 70%)" }}
      />
      <div
        className="pointer-events-none absolute -left-32 bottom-0 size-[360px] rounded-full blur-3xl"
        style={{ background: "radial-gradient(circle, oklch(0.78 0.16 152 / 0.12), transparent 70%)" }}
      />

      <div className="relative z-10 flex items-center justify-between">
        <LeadScopeWordmark />
        <div className="flex items-center gap-1.5 rounded-full border border-border bg-background/60 px-2.5 py-1 text-[11px] font-medium text-muted-foreground backdrop-blur">
          <Lock className="size-3 text-[oklch(var(--signal))]" />
          SOC 2 · Type II
        </div>
      </div>

      <div className="relative z-10 flex flex-col gap-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <h1 className="text-pretty text-[34px] font-semibold leading-[1.1] tracking-tight text-foreground">
            The evidence-first lead intelligence platform for serious agency operators.
          </h1>
          <p className="mt-4 max-w-md text-pretty text-[15px] leading-relaxed text-muted-foreground">
            Discover leads, normalize provider data, score deterministically, and ship assistive outreach — with every
            decision traceable to source facts.
          </p>
        </motion.div>

        <div className="flex flex-col gap-3">
          {PROOF_POINTS.map((pt, i) => {
            const Icon = pt.icon;
            return (
              <motion.div
                key={pt.title}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 + i * 0.08, duration: 0.5 }}
                className="flex gap-3 rounded-lg border border-border/80 bg-card/50 p-3 backdrop-blur"
              >
                <div className="flex size-9 shrink-0 items-center justify-center rounded-md border border-[oklch(var(--signal)/0.25)] bg-[oklch(var(--signal)/0.08)] text-[oklch(var(--signal))]">
                  <Icon className="size-4" />
                </div>
                <div className="min-w-0">
                  <div className="text-[13px] font-medium text-foreground">{pt.title}</div>
                  <div className="text-[12px] leading-relaxed text-muted-foreground">{pt.body}</div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>

      <div className="relative z-10 flex items-center justify-between text-[11px] text-muted-foreground">
        <div className="flex items-center gap-4">
          <span>Trusted by 1,400+ agency teams</span>
        </div>
        <div className="flex items-center gap-3 font-mono tracking-wider">
          <span>v12.4</span>
          <span>·</span>
          <span>us-west</span>
        </div>
      </div>
    </aside>
  );
}
