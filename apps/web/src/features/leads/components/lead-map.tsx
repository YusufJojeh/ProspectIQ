import { memo, useEffect, useMemo } from "react";
import { divIcon } from "leaflet";
import "leaflet/dist/leaflet.css";
import { Marker, Popup, useMap } from "react-leaflet";
import { useTranslation } from "react-i18next";
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
import { leadStatusLabel, scoreBandLabel } from "@/lib/i18n-labels";
import { formatScore } from "@/lib/presenters";
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

    map.fitBounds(
      leads.map((lead) => toLatLngTuple(lead)),
      {
        padding: DEFAULT_MAP_FIT_PADDING,
        maxZoom: DEFAULT_MAP_SELECTED_POINT_ZOOM,
      },
    );
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
  const { t } = useTranslation();
  const markerIcon = useMemo(
    () => createLeadMarkerIcon(isSelected),
    [isSelected],
  );
  const eventHandlers = useMemo(
    () => (onSelect ? { click: () => onSelect(lead.public_id) } : undefined),
    [lead.public_id, onSelect],
  );

  return (
    <Marker
      eventHandlers={eventHandlers}
      icon={markerIcon}
      position={toLatLngTuple(lead)}
      zIndexOffset={isSelected ? 1000 : 0}
    >
      <Popup closeButton={false}>
        <div className="min-w-[220px] overflow-hidden rounded-xl bg-popover text-popover-foreground shadow-lg">
          <div className="border-b border-border bg-muted/30 px-3 py-2">
            <p className="line-clamp-2 text-sm font-semibold leading-5">
              {lead.company_name}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {lead.city ?? t("dashboard.unknownCity")}
            </p>
          </div>
          <div className="grid gap-2 p-3 text-xs text-muted-foreground">
            <PopupFact
              label={t("leads.score")}
              value={formatScore(lead.latest_score)}
            />
            <PopupFact
              label={t("leads.band")}
              value={scoreBandLabel(t, lead.latest_band)}
            />
            <PopupFact
              label={t("leads.status")}
              value={
                lead.status
                  ? leadStatusLabel(t, lead.status)
                  : t("common.unknown")
              }
            />
            <PopupFact
              label={t("leads.website")}
              value={lead.website_domain ?? t("leads.missing")}
            />
          </div>
          <a
            className="block border-t border-border px-3 py-2 text-xs font-medium text-[oklch(var(--signal))] hover:bg-muted/30"
            href={`https://www.google.com/maps/search/?api=1&query=${lead.lat},${lead.lng}`}
            rel="noreferrer"
            target="_blank"
          >
            {t("leads.openInGoogleMaps", {
              defaultValue: "Open in Google Maps",
            })}
          </a>
        </div>
      </Popup>
    </Marker>
  );
});

function PopupFact({ label, value }: { label: string; value: string }) {
  return (
    <p className="flex items-center justify-between gap-3">
      <span className="font-medium text-foreground">{label}</span>
      <span className="max-w-[130px] truncate text-right">{value}</span>
    </p>
  );
}

function createLeadMarkerIcon(isSelected: boolean) {
  return divIcon({
    className: `lead-map-marker${isSelected ? " is-selected" : ""}`,
    html: '<span class="lead-map-marker__pulse"></span><span class="lead-map-marker__pin"></span>',
    iconAnchor: [16, 32],
    iconSize: [32, 32],
    popupAnchor: [0, -30],
  });
}

export function LeadMap({
  leads,
  selectedLeadId,
  onSelect,
  className,
}: LeadMapProps) {
  const { t } = useTranslation();
  const mappable = useMemo(
    () => leads.filter(hasCoordinates) as MappableLeadMapPoint[],
    [leads],
  );

  return (
    <div
      className={cn("h-full", className)}
      role="region"
      aria-label={t("leads.mapLabel")}
    >
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
