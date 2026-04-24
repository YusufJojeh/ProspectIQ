import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export interface HeroVideoProps {
  /** Path to the video file (mp4 preferred) */
  src?: string;
  /** Path to the WebM variant for better compression */
  srcWebm?: string;
  /** Poster image shown while video loads or as fallback */
  poster?: string;
  /** Static fallback image when no video is provided */
  fallbackImage?: string;
  /** Alt text for the fallback image */
  fallbackAlt?: string;
  /** Additional class names for the container */
  className?: string;
  /** Overlay gradient variant */
  overlay?: "hero" | "panel" | "subtle" | "none";
  /** Aspect ratio class override */
  aspect?: string;
}

const overlayStyles: Record<string, string> = {
  hero: "bg-gradient-to-t from-[#090b12] via-[#090b12]/60 to-transparent",
  panel: "bg-gradient-to-br from-[#090b12]/80 via-[#090b12]/40 to-[#090b12]/70",
  subtle: "bg-[#090b12]/30",
  none: "",
};

export function HeroVideo({
  src,
  srcWebm,
  poster,
  fallbackImage,
  fallbackAlt = "Product visual",
  className,
  overlay = "hero",
  aspect,
}: HeroVideoProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [videoFailed, setVideoFailed] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);
  const hasVideo = (src || srcWebm) && !videoFailed;

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          video.play().catch(() => {});
        } else {
          video.pause();
        }
      },
      { threshold: 0.15 },
    );

    observer.observe(video);
    return () => observer.disconnect();
  }, [hasVideo]);

  return (
    <div
      className={cn(
        "relative overflow-hidden",
        aspect ?? "aspect-video",
        className,
      )}
    >
      {hasVideo ? (
        <video
          ref={videoRef}
          className={cn(
            "absolute inset-0 h-full w-full object-cover transition-opacity duration-700",
            isLoaded ? "opacity-100" : "opacity-0",
          )}
          poster={poster}
          muted
          loop
          playsInline
          preload="metadata"
          onCanPlay={() => setIsLoaded(true)}
          onError={() => setVideoFailed(true)}
        >
          {srcWebm && <source src={srcWebm} type="video/webm" />}
          {src && <source src={src} type="video/mp4" />}
        </video>
      ) : null}

      {(!hasVideo && fallbackImage) ? (
        <img
          src={fallbackImage}
          alt={fallbackAlt}
          className="absolute inset-0 h-full w-full object-cover"
          loading="lazy"
          decoding="async"
        />
      ) : null}

      {!hasVideo && !fallbackImage ? (
        <MediaPlaceholder />
      ) : null}

      {/* Poster shimmer while video loads */}
      {hasVideo && !isLoaded && poster ? (
        <img
          src={poster}
          alt=""
          aria-hidden
          className="absolute inset-0 h-full w-full object-cover"
        />
      ) : null}

      {hasVideo && !isLoaded && !poster ? (
        <MediaPlaceholder />
      ) : null}

      {overlay !== "none" && (
        <div className={cn("pointer-events-none absolute inset-0", overlayStyles[overlay])} />
      )}
    </div>
  );
}

function MediaPlaceholder() {
  return (
    <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-[#0f172a] via-[#0d1525] to-[#090b12]">
      <div className="relative">
        <div className="absolute -inset-20 rounded-full bg-[radial-gradient(circle,rgba(20,184,166,0.15),transparent_70%)]" />
        <div className="relative flex flex-col items-center gap-3 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-white/5 backdrop-blur">
            <svg className="h-7 w-7 text-teal-400/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z" />
            </svg>
          </div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">
            Media asset slot
          </p>
        </div>
      </div>
    </div>
  );
}
