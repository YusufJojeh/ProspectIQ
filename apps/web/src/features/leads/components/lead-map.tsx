import { memo, useEffect, useMemo } from "react";
import "leaflet/dist/leaflet.css";
import { CircleMarker, Popup, useMap } from "react-leaflet";
import { LeafletMapShell } from "@/components/maps/leaflet-map-shell";
import {
  DEFAULT_MAP_CENTER,
  DEFAULT_MAP_FIT_PADDING,
  DEFAULT_MAP_SELECTED_POINT_ZOOM,
  DEFAULT_MAP_SINGLE_POINT_ZOOM,
  DEFAULT_MAP_ZOOM,
  hasCoordinates,
  toLatLngTuple,
} from "@/lib/maps";
import { formatScore, titleCaseLabel } from "@/lib/presenters";
import { cn } from "@/lib/utils";
import type { LeadScoreBand, LeadStatus } from "@/types/api";

type LeadMapPoint = {
  public_id: string;
  company_name: string;
  city: string | null;
  latest_score: number | null;
  latest_band?: LeadScoreBand | null;
  status?: LeadStatus;
  website_domain?: string | null;
  lat: number | null;
  lng: number | null;
};

type LeadMapProps = {
  leads: LeadMapPoint[];
  selectedLeadId?: string | null;
  onSelect?: (leadId: string) => void;
  className?: string;
};

type MappableLeadMapPoint = LeadMapPoint & {
  lat: number;
  lng: number;
};

const SELECTED_MARKER_STYLE = {
  color: "var(--accent-ink)",
  fillColor: "var(--warning)",
  fillOpacity: 0.85,
  weight: 3,
} as const;

const DEFAULT_MARKER_STYLE = {
  color: "var(--accent)",
  fillColor: "var(--accent)",
  fillOpacity: 0.85,
  weight: 2,
} as const;

const MapViewport = memo(function MapViewport({
  leads,
  selectedLeadId,
}: {
  leads: MappableLeadMapPoint[];
  selectedLeadId?: string | null;
}) {
  const map = useMap();

  useEffect(() => {
    if (leads.length === 0) {
      map.setView(DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM);
      return;
    }

    const selected = leads.find((lead) => lead.public_id === selectedLeadId);
    if (selected) {
      map.setView(toLatLngTuple(selected), DEFAULT_MAP_SELECTED_POINT_ZOOM);
      return;
    }

    if (leads.length === 1) {
      map.setView(toLatLngTuple(leads[0]), DEFAULT_MAP_SINGLE_POINT_ZOOM);
      return;
    }

    map.fitBounds(leads.map((lead) => toLatLngTuple(lead)), {
      padding: DEFAULT_MAP_FIT_PADDING,
      maxZoom: DEFAULT_MAP_SELECTED_POINT_ZOOM,
    });
  }, [leads, map, selectedLeadId]);

  return null;
});

const LeadMarker = memo(function LeadMarker({
  lead,
  isSelected,
  onSelect,
}: {
  lead: MappableLeadMapPoint;
  isSelected: boolean;
  onSelect?: (leadId: string) => void;
}) {
  const markerStyle = isSelected ? SELECTED_MARKER_STYLE : DEFAULT_MARKER_STYLE;
  const eventHandlers = useMemo(
    () => (onSelect ? { click: () => onSelect(lead.public_id) } : undefined),
    [lead.public_id, onSelect],
  );

  return (
    <CircleMarker
      center={toLatLngTuple(lead)}
      pathOptions={markerStyle}
      radius={isSelected ? 10 : 7}
      eventHandlers={eventHandlers}
    >
      <Popup>
        <div className="space-y-2 p-3">
          <div>
            <p className="font-semibold">{lead.company_name}</p>
            <p className="text-xs text-[color:var(--muted)]">{lead.city ?? "Unknown city"}</p>
          </div>
          <div className="grid gap-1 text-xs text-[color:var(--muted)]">
            <p>
              <span className="font-semibold text-[color:var(--text)]">Score:</span>{" "}
              {formatScore(lead.latest_score)}
            </p>
            <p>
              <span className="font-semibold text-[color:var(--text)]">Band:</span>{" "}
              {lead.latest_band ? titleCaseLabel(lead.latest_band) : "Unscored"}
            </p>
            <p>
              <span className="font-semibold text-[color:var(--text)]">Status:</span>{" "}
              {lead.status ? titleCaseLabel(lead.status) : "Unknown"}
            </p>
            <p>
              <span className="font-semibold text-[color:var(--text)]">Website:</span>{" "}
              {lead.website_domain ?? "Missing"}
            </p>
          </div>
        </div>
      </Popup>
    </CircleMarker>
  );
});

export function LeadMap({ leads, selectedLeadId, onSelect, className }: LeadMapProps) {
  const mappable = useMemo(() => leads.filter(hasCoordinates) as MappableLeadMapPoint[], [leads]);

  return (
    <div className={cn("h-full", className)} role="region" aria-label="Lead map">
      <LeafletMapShell scrollWheelZoom={false}>
        <MapViewport leads={mappable} selectedLeadId={selectedLeadId} />
        {mappable.map((lead) => {
          return (
            <LeadMarker
              key={lead.public_id}
              lead={lead}
              isSelected={lead.public_id === selectedLeadId}
              onSelect={onSelect}
            />
          );
        })}
      </LeafletMapShell>
    </div>
  );
}
