import type { BrandFields } from "@/types/proposals";

/** A brand's mark (or logo) on its paper colour, with its accent colours. */
export function BrandSwatch({ brand, size = "md" }: { brand: BrandFields; size?: "sm" | "md" }) {
  const box = size === "sm" ? "size-9" : "size-12";
  return (
    <div className="flex items-center gap-2">
      <div
        className={`${box} grid shrink-0 place-items-center overflow-hidden rounded-lg ring-1 ring-black/10`}
        style={{ background: brand.paper, color: brand.accent }}
        aria-hidden
      >
        {brand.logo_data_url ? (
          <img src={brand.logo_data_url} alt="" className="max-h-[80%] max-w-[80%] object-contain" />
        ) : (
          <span className="font-mono text-xs font-bold">{brand.mark || brand.name.slice(0, 2)}</span>
        )}
      </div>
      <div className="flex flex-col gap-1" aria-hidden>
        <span className="h-2 w-6 rounded-full" style={{ background: brand.accent }} />
        <span className="h-2 w-6 rounded-full" style={{ background: brand.accent_secondary }} />
        <span className="h-2 w-6 rounded-full" style={{ background: brand.ink }} />
      </div>
    </div>
  );
}
