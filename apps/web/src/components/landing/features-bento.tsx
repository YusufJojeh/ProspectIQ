"use client";

import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import {
  Database,
  GitBranch,
  Layers,
  Radar,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";

type FeatureCopy = { title: string; body: string };

export function FeaturesBento() {
  const { t } = useTranslation();
  const cards = t("landing.features.cards", {
    returnObjects: true,
  }) as FeatureCopy[];

  return (
    <section id="platform" className="relative py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <SectionHeader
          eyebrow={t("landing.features.eyebrow")}
          title={t("landing.features.title")}
          description={t("landing.features.description")}
        />

        <div className="mt-16 grid grid-cols-1 gap-4 md:grid-cols-6 md:auto-rows-[180px]">
          <FeatureCard
            className="md:col-span-4 md:row-span-2"
            icon={Radar}
            title={cards[0].title}
            body={cards[0].body}
            visual={<DiscoveryVisual />}
          />
          <FeatureCard
            className="md:col-span-2 md:row-span-1"
            icon={Layers}
            title={cards[1].title}
            body={cards[1].body}
          />
          <FeatureCard
            className="md:col-span-2 md:row-span-1"
            icon={Zap}
            title={cards[2].title}
            body={cards[2].body}
          />
          <FeatureCard
            className="md:col-span-2 md:row-span-1"
            icon={ShieldCheck}
            title={cards[3].title}
            body={cards[3].body}
          />
          <FeatureCard
            className="md:col-span-2 md:row-span-1"
            icon={GitBranch}
            title={cards[4].title}
            body={cards[4].body}
          />
          <FeatureCard
            className="md:col-span-2 md:row-span-1"
            icon={Database}
            title={cards[5].title}
            body={cards[5].body}
          />
          <FeatureCard
            className="md:col-span-6 md:row-span-1"
            icon={Sparkles}
            title={cards[6].title}
            body={cards[6].body}
            visual={<OutreachVisual />}
          />
        </div>
      </div>
    </section>
  );
}

function SectionHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.6 }}
      className="mx-auto flex max-w-2xl flex-col items-center text-center"
    >
      <div className="inline-flex items-center gap-2 rounded-full border border-[oklch(var(--signal)/0.3)] bg-[oklch(var(--signal)/0.08)] px-2.5 py-0.5 text-[11px] font-medium text-[oklch(var(--signal))]">
        {eyebrow}
      </div>
      <h2 className="mt-4 text-pretty text-[36px] font-semibold leading-[1.1] tracking-tight sm:text-[44px]">
        {title}
      </h2>
      <p className="mt-4 text-pretty text-base leading-relaxed text-muted-foreground">
        {description}
      </p>
    </motion.div>
  );
}

function FeatureCard({
  className,
  icon: Icon,
  title,
  body,
  visual,
}: {
  className?: string;
  icon: React.ElementType;
  title: string;
  body: string;
  visual?: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className={`group relative flex flex-col overflow-hidden rounded-2xl border border-border bg-card/60 p-5 backdrop-blur-sm transition-colors hover:border-[oklch(var(--signal)/0.35)] ${className ?? ""}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex size-8 items-center justify-center rounded-md border border-[oklch(var(--signal)/0.25)] bg-[oklch(var(--signal)/0.08)] text-[oklch(var(--signal))]">
          <Icon className="size-4" />
        </div>
      </div>
      <h3 className="mt-4 text-[15px] font-semibold tracking-tight text-foreground">
        {title}
      </h3>
      <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
        {body}
      </p>
      {visual ? <div className="mt-4 flex-1">{visual}</div> : null}
    </motion.div>
  );
}

function DiscoveryVisual() {
  const rows = [
    { name: "Northbeam Analytics", score: 87, tone: "oklch(var(--signal))" },
    { name: "Brightwave Studio", score: 74, tone: "oklch(var(--evidence))" },
    { name: "Apex Signals", score: 68, tone: "oklch(var(--caution))" },
    { name: "Parallax HQ", score: 55, tone: "oklch(var(--risk))" },
  ];
  const { t } = useTranslation();

  return (
    <div className="relative h-full w-full overflow-hidden rounded-xl border border-border bg-background/60 p-4">
      <div className="mb-3 flex items-center justify-between text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
        <span>{t("landing.features.visual.searchTitle")}</span>
        <span className="font-mono">
          {t("landing.features.visual.searchMeta")}
        </span>
      </div>
      <div className="flex flex-col gap-2">
        {rows.map((r, i) => (
          <motion.div
            key={r.name}
            initial={{ opacity: 0, x: -10 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 + i * 0.1 }}
            className="flex items-center gap-3 rounded-lg border border-border bg-card/60 px-3 py-2"
          >
            <div className="font-mono text-[10px] text-muted-foreground">
              #{i + 1}
            </div>
            <div className="flex-1 truncate text-[12px] font-medium text-foreground">
              {r.name}
            </div>
            <div className="h-1 w-16 overflow-hidden rounded-full bg-border">
              <motion.div
                initial={{ width: 0 }}
                whileInView={{ width: `${r.score}%` }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 + i * 0.1, duration: 0.8 }}
                className="h-full rounded-full"
                style={{ background: r.tone }}
              />
            </div>
            <div className="w-8 text-right font-mono text-[11px] text-foreground">
              {r.score}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

function OutreachVisual() {
  const { t } = useTranslation();
  const citations = t("landing.features.visual.citations", {
    returnObjects: true,
  }) as string[];

  return (
    <div className="relative grid grid-cols-1 gap-3 md:grid-cols-2">
      <div className="rounded-xl border border-border bg-background/60 p-3">
        <div className="mb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
          {t("landing.features.visual.draftTitle")}
        </div>
        <p className="text-[12px] leading-relaxed text-foreground">
          {t("landing.features.visual.draftCopyPrefix")}{" "}
          <span className="rounded bg-[oklch(var(--signal)/0.15)] px-1 text-[oklch(var(--signal))]">
            {t("landing.features.visual.draftHighlightFunding")}
          </span>{" "}
          {t("landing.features.visual.draftMiddle")}{" "}
          <span className="rounded bg-[oklch(var(--evidence)/0.15)] px-1 text-[oklch(var(--evidence))]">
            {t("landing.features.visual.draftHighlightHiring")}
          </span>{" "}
          {t("landing.features.visual.draftSuffix")}
        </p>
      </div>
      <div className="rounded-xl border border-border bg-background/60 p-3">
        <div className="mb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
          {t("landing.features.visual.citationsTitle")}
        </div>
        <div className="flex flex-col gap-1.5 text-[11px] text-muted-foreground">
          {citations.map((item) => (
            <div key={item}>- {item}</div>
          ))}
        </div>
      </div>
    </div>
  );
}
