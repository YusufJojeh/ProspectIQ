import { useEffect } from "react";
import { CircleMarker, Popup, useMap } from "react-leaflet";
import { LeafletMapShell } from "@/components/maps/leaflet-map-shell";
import {
  DEFAULT_MAP_CENTER,
  DEFAULT_MAP_FIT_PADDING,
  DEFAULT_MAP_ZOOM,
  hasCoordinates,
  toLatLngTuple,
} from "@/lib/maps";
import { cn } from "@/lib/utils";

type LeadMapPoint = {
  public_id: string;
  company_name: string;
  city: string | null;
  latest_score: number | null;
  lat: number | null;
  lng: number | null;
};

type LeadMapProps = {
  leads: LeadMapPoint[];
  selectedLeadId?: string | null;
  onSelect?: (leadId: string) => void;
  className?: string;
};

function MapViewport({ leads, selectedLeadId }: { leads: LeadMapPoint[]; selectedLeadId?: string | null }) {
  const map = useMap();

  useEffect(() => {
    const mappable = leads.filter(hasCoordinates);
    if (mappable.length === 0) {
      map.setView(DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM);
      return;
    }

    const selected = mappable.find((lead) => lead.public_id === selectedLeadId);
    if (selected) {
      map.flyTo(toLatLngTuple(selected), 13, { duration: 0.7 });
      return;
    }

    map.fitBounds(mappable.map((lead) => toLatLngTuple(lead)), {
      padding: DEFAULT_MAP_FIT_PADDING,
    });
  }, [leads, map, selectedLeadId]);

  return null;
}

export function LeadMap({ leads, selectedLeadId, onSelect, className }: LeadMapProps) {
  const mappable = leads.filter(hasCoordinates);

  return (
    <div className={cn("h-full", className)} role="region" aria-label="Lead map">
      <LeafletMapShell scrollWheelZoom={false}>
        <MapViewport leads={mappable} selectedLeadId={selectedLeadId} />
        {mappable.map((lead) => {
          const isSelected = lead.public_id === selectedLeadId;
          return (
            <CircleMarker
              key={lead.public_id}
              center={toLatLngTuple(lead)}
              pathOptions={{
                color: isSelected ? "var(--accent-ink)" : "var(--accent)",
                fillColor: isSelected ? "var(--warning)" : "var(--accent)",
                fillOpacity: 0.85,
                weight: isSelected ? 3 : 2,
              }}
              radius={isSelected ? 10 : 7}
              eventHandlers={onSelect ? { click: () => onSelect(lead.public_id) } : undefined}
            >
              <Popup>
                <div className="space-y-1">
                  <p className="font-semibold">{lead.company_name}</p>
                  <p className="text-xs text-slate-500">{lead.city ?? "Unknown city"}</p>
                  <p className="text-xs text-slate-500">
                    Score {lead.latest_score ? Math.round(lead.latest_score) : "N/A"}
                  </p>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </LeafletMapShell>
    </div>
  );
}
