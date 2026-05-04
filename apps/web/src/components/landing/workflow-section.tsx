"use client";

import { useLayoutEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Radar, Layers, Gauge, Send } from "lucide-react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

const STEP_ICONS = [Radar, Layers, Gauge, Send];

export function WorkflowSection() {
  const { t } = useTranslation();
  const steps = t("landing.workflow.steps", { returnObjects: true }) as Array<{ title: string; body: string }>;
  const rootRef = useRef<HTMLElement | null>(null);

  useLayoutEffect(() => {
    if (!rootRef.current) return;

    gsap.registerPlugin(ScrollTrigger);
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (media.matches) return;

    const context = gsap.context(() => {
      gsap.from("[data-workflow-header]", {
        opacity: 0,
        y: 24,
        duration: 0.7,
        ease: "power3.out",
        scrollTrigger: { trigger: rootRef.current, start: "top 72%", once: true },
      });

      gsap.fromTo(
        "[data-workflow-connector]",
        { scaleX: 0, transformOrigin: "center center" },
        {
          scaleX: 1,
          duration: 0.9,
          ease: "power2.inOut",
          scrollTrigger: { trigger: "[data-workflow-rail]", start: "top 78%", once: true },
        },
      );

      gsap.from("[data-workflow-step]", {
        opacity: 0,
        y: 28,
        stagger: 0.12,
        duration: 0.68,
        ease: "expo.out",
        scrollTrigger: { trigger: "[data-workflow-rail]", start: "top 72%", once: true },
      });
    }, rootRef);

    return () => context.revert();
  }, []);

  return (
    <section ref={rootRef} id="workflow" className="relative py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <div data-workflow-header className="mx-auto flex max-w-2xl flex-col items-center text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/40 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground">
            {t("landing.workflow.eyebrow")}
          </div>
          <h2 className="mt-4 text-pretty text-[36px] font-semibold leading-[1.1] tracking-tight sm:text-[44px]">{t("landing.workflow.title")}</h2>
        </div>

        <div data-workflow-rail className="relative mt-20">
          <div className="pointer-events-none absolute left-0 right-0 top-[27px] hidden h-px lg:block">
            <div data-workflow-connector className="mx-auto h-full max-w-5xl bg-gradient-to-r from-transparent via-border to-transparent" />
          </div>

          <div className="grid grid-cols-1 gap-8 lg:grid-cols-4 lg:gap-6">
            {steps.map((step, index) => {
              const Icon = STEP_ICONS[index] ?? Send;
              const stepNumber = String(index + 1).padStart(2, "0");
              return (
                <article key={stepNumber} data-workflow-step className="relative flex flex-col">
                  <div className="relative mb-6 flex size-14 items-center justify-center rounded-2xl border border-border bg-card">
                    <div
                      className="absolute inset-0 rounded-2xl"
                      style={{ background: "radial-gradient(circle at 30% 20%, oklch(0.82 0.14 195 / 0.15), transparent 60%)" }}
                    />
                    <Icon className="size-5 text-[oklch(var(--signal))]" />
                  </div>
                  <div className="mb-2 font-mono text-[11px] font-medium tracking-[0.14em] text-muted-foreground">
                    {t("landing.workflow.stepLabel")} {stepNumber}
                  </div>
                  <h3 className="text-[18px] font-semibold tracking-tight text-foreground">{step.title}</h3>
                  <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{step.body}</p>
                </article>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
