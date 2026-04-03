import type { PropsWithChildren } from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import {
  DEFAULT_MAP_CENTER,
  DEFAULT_MAP_TILE_ATTRIBUTION,
  DEFAULT_MAP_TILE_URL,
  DEFAULT_MAP_ZOOM,
  type MapLatLng,
} from "@/lib/maps";
import { cn } from "@/lib/utils";

type LeafletMapShellProps = PropsWithChildren<{
  center?: MapLatLng;
  className?: string;
  scrollWheelZoom?: boolean;
  zoom?: number;
}>;

export function LeafletMapShell({
  center = DEFAULT_MAP_CENTER,
  children,
  className,
  scrollWheelZoom = false,
  zoom = DEFAULT_MAP_ZOOM,
}: LeafletMapShellProps) {
  return (
    <div className={cn("h-full w-full overflow-hidden rounded-[inherit]", className)}>
      <MapContainer center={center} zoom={zoom} scrollWheelZoom={scrollWheelZoom} className="h-full w-full">
        <TileLayer attribution={DEFAULT_MAP_TILE_ATTRIBUTION} url={DEFAULT_MAP_TILE_URL} />
        {children}
      </MapContainer>
    </div>
  );
}
