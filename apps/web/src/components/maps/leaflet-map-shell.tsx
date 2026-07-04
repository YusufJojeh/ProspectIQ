import type { PropsWithChildren } from "react";
import {
  AttributionControl,
  MapContainer,
  TileLayer,
  ZoomControl,
} from "react-leaflet";
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
    <div
      dir="ltr"
      className={cn(
        "h-full w-full overflow-hidden rounded-[inherit] border border-border bg-card shadow-[0_18px_40px_-30px_rgba(0,0,0,0.25),inset_0_1px_0_rgba(255,255,255,0.03)]",
        className,
      )}
    >
      <MapContainer
        attributionControl={false}
        center={center}
        className="h-full w-full"
        preferCanvas
        scrollWheelZoom={scrollWheelZoom}
        zoom={zoom}
        zoomControl={false}
      >
        <TileLayer
          attribution={DEFAULT_MAP_TILE_ATTRIBUTION}
          detectRetina
          maxZoom={19}
          url={DEFAULT_MAP_TILE_URL}
        />
        <ZoomControl position="topright" />
        <AttributionControl position="bottomright" prefix={false} />
        {children}
      </MapContainer>
    </div>
  );
}
