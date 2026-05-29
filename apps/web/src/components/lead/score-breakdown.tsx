import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Badge } from "@/components/ui/badge";
import { useTranslation } from "react-i18next";

type BreakdownItem = {
  key: string;
  label: string;
  weight: number;
  contribution: number;
  reason: string;
  percent: number;
};

function barColor(contribution: number, weight: number): string {
  const maxContrib = weight * 100;
  const pct = maxContrib > 0 ? (contribution / maxContrib) * 100 : 0;
  if (pct >= 60) return "oklch(var(--success))";
  if (pct >= 30) return "oklch(var(--caution))";
  return "oklch(var(--destructive))";
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: BreakdownItem }> }) {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;
  const maxContrib = item.weight * 100;
  return (
    <div className="max-w-[260px] rounded-xl border border-border bg-card p-3 text-sm shadow-lg">
      <p className="font-semibold">{item.label}</p>
      <p className="mt-1 text-muted-foreground">{item.reason}</p>
      <div className="mt-2 flex items-center justify-between gap-4 font-mono text-xs tabular-nums">
        <span>{item.contribution.toFixed(1)} / {maxContrib.toFixed(0)}</span>
        <span className="text-muted-foreground">{item.percent}% of total</span>
      </div>
    </div>
  );
}

export function LeadScoreBreakdownCard({
  totalScore,
  qualified,
  scoringVersionId,
  items,
}: {
  totalScore: number;
  qualified: boolean;
  scoringVersionId?: string | null;
  items: BreakdownItem[];
}) {
  const { t } = useTranslation();

  const chartData = items.map((item) => ({
    ...item,
    maxContrib: Math.round(item.weight * 100),
  }));

  return (
    <section className="rounded-2xl border border-border bg-card/95">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-4">
        <div>
          <h2 className="text-sm font-semibold">{t("leads.scoreBreakdown")}</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("leadDetail.scoreBreakdownDescription")}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {scoringVersionId ? <Badge tone="neutral">{scoringVersionId}</Badge> : null}
          <Badge tone={qualified ? "success" : "warning"}>
            {qualified ? t("leads.qualified") : t("leadDetail.belowThreshold")}
          </Badge>
          <Badge tone="accent">{totalScore}</Badge>
        </div>
      </header>

      {/* Stacked total bar */}
      {items.length > 0 && (
        <div className="px-4 pt-4">
          <div className="h-3 overflow-hidden rounded-full bg-muted">
            <div className="flex h-full">
              {items.map((item) => (
                <div
                  key={item.key}
                  title={`${item.label}: ${item.contribution.toFixed(1)}`}
                  className="h-full transition-all"
                  style={{
                    width: `${item.percent}%`,
                    backgroundColor: barColor(item.contribution, item.weight),
                  }}
                />
              ))}
            </div>
          </div>
          <div className="mt-1 flex justify-between font-mono text-[10px] text-muted-foreground">
            <span>0</span>
            <span>{Math.round(totalScore)} / 100</span>
          </div>
        </div>
      )}

      {/* Horizontal bar chart */}
      <div className="px-4 pb-2 pt-3">
        <ResponsiveContainer width="100%" height={items.length * 44 + 20}>
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 0, right: 12, bottom: 0, left: 0 }}
          >
            <XAxis type="number" domain={[0, 25]} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
            <YAxis
              type="category"
              dataKey="label"
              width={108}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "oklch(var(--muted)/0.4)" }} />
            <Bar dataKey="contribution" radius={4} maxBarSize={20}>
              {chartData.map((item) => (
                <Cell key={item.key} fill={barColor(item.contribution, item.weight)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-3 border-t border-border px-4 py-2">
        {[
          { label: t("leadDetail.strengthStrong"), color: "oklch(var(--success))" },
          { label: t("leadDetail.strengthModerate"), color: "oklch(var(--caution))" },
          { label: t("leadDetail.strengthWeak"), color: "oklch(var(--destructive))" },
        ].map(({ label, color }) => (
          <div key={label} className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <span className="size-2 rounded-full" style={{ backgroundColor: color }} />
            {label}
          </div>
        ))}
      </div>
    </section>
  );
}
