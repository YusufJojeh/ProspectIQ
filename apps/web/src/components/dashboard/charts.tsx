import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const tooltipStyle = {
  background: "var(--panel)",
  border: "1px solid var(--border)",
  borderRadius: 12,
  color: "var(--text)",
  fontSize: 12,
  padding: "8px 10px",
};

export function JobThroughputChart({
  data,
}: {
  data: Array<{ label: string; discovered: number; qualified: number }>;
}) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <defs>
          <linearGradient id="jobs-discovered" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="oklch(var(--signal))" stopOpacity="0.32" />
            <stop offset="100%" stopColor="oklch(var(--signal))" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="jobs-qualified" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="oklch(var(--evidence))" stopOpacity="0.3" />
            <stop offset="100%" stopColor="oklch(var(--evidence))" stopOpacity="0" />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="oklch(var(--border))" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" stroke="oklch(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
        <YAxis stroke="oklch(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Area type="monotone" dataKey="discovered" stroke="oklch(var(--signal))" fill="url(#jobs-discovered)" strokeWidth={2} />
        <Area type="monotone" dataKey="qualified" stroke="oklch(var(--evidence))" fill="url(#jobs-qualified)" strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function ScoreDistributionChart({
  data,
}: {
  data: Array<{ band: string; count: number; fill: string }>;
}) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid stroke="oklch(var(--border))" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="band" stroke="oklch(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
        <YAxis stroke="oklch(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Bar dataKey="count" radius={[6, 6, 0, 0]}>
          {data.map((item) => (
            <Cell key={item.band} fill={item.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
