import type { UiSlide } from "@/types/project";
const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8100";

interface SlidePreviewProps {
  format: "carousel" | "stories_10x";
  data: UiSlide;
  settings: { author_name: string; handle: string; brand_color: string };
}

export default function SlidePreview({ format, data, settings }: SlidePreviewProps) {
  const isCarousel = format === "carousel";
  const bullets = data.bullets || [];

  // Resolve appearance for preview
  const appearance = data.appearance;
  const effectiveTheme = appearance?.theme === "dark" ? "dark"
    : appearance?.theme === "light" ? "light"
    : null; // auto = no override
  const isDarkPreview = effectiveTheme === "dark";
  const scrim = appearance?.scrim;
  const scrimActive = scrim?.enabled && data.image_path;

  // Build scrim gradient for preview
  let scrimStyle: React.CSSProperties = {};
  if (scrimActive && scrim) {
    const alpha = scrim.strength || 0.35;
    const baseColor = isDarkPreview
      ? `rgba(0,0,0,${alpha})`
      : `rgba(0,0,0,${alpha})`;
    const fade = "rgba(0,0,0,0)";

    let gradient: string;
    if (scrim.mode === "box") {
      gradient = baseColor;
    } else {
      if (scrim.position === "top") {
        gradient = `linear-gradient(to bottom, ${baseColor} 0%, ${baseColor} 30%, ${fade} 70%)`;
      } else if (scrim.position === "center") {
        gradient = `linear-gradient(to bottom, ${fade} 0%, ${baseColor} 25%, ${baseColor} 75%, ${fade} 100%)`;
      } else {
        gradient = `linear-gradient(to top, ${baseColor} 0%, ${baseColor} 30%, ${fade} 70%)`;
      }
    }
    scrimStyle = {
      position: "absolute" as const,
      inset: 0,
      background: gradient,
      zIndex: 1,
      pointerEvents: "none" as const,
      borderRadius: "inherit",
    };
  }

  return (
    <div
      className={`relative overflow-hidden rounded-lg border ${
        isDarkPreview ? "bg-zinc-900 text-zinc-100" : "bg-card text-foreground"
      } ${isCarousel ? "slide-preview-carousel" : "slide-preview-story"}`}
      style={{ maxWidth: isCarousel ? 270 : 180 }}
    >
      {/* Background image or color */}
      {(data.image_path) ? (
        <img
          src={data.image_path ? `${API_BASE}/${data.image_path}` : ""}
          alt=""
          className="absolute inset-0 w-full h-full object-cover"
        />
      ) : (
        <div
          className="absolute inset-0"
          style={{
            background: isDarkPreview
              ? `linear-gradient(135deg, ${settings.brand_color}15 0%, #0f0f10 100%)`
              : `linear-gradient(135deg, ${settings.brand_color}22 0%, ${settings.brand_color}08 100%)`,
          }}
        />
      )}

      {/* Scrim overlay */}
      {scrimActive && <div style={scrimStyle} />}

      {/* Content overlay */}
      <div className="relative h-full flex flex-col justify-between p-4" style={{ zIndex: 2 }}>
        {/* Top */}
        <div className="space-y-1.5">
          {isCarousel && data.role === "cover" && (
            <span className={`text-[9px] font-semibold uppercase tracking-widest ${isDarkPreview ? "text-zinc-400" : "text-primary"}`}>
              {settings.handle}
            </span>
          )}
          <h3 className="text-sm font-bold leading-snug line-clamp-3">
            {data.headline}
          </h3>
          {(data.subhead || data.support) && (
            <p className={`text-[10px] leading-tight line-clamp-2 ${isDarkPreview ? "text-zinc-400" : "text-muted-foreground"}`}>
              {data.subhead || data.support}
            </p>
          )}
        </div>

        {/* Middle */}
        <div className="flex-1 flex items-center">
          {isCarousel && data.body && (
            <p className={`text-[9px] leading-relaxed line-clamp-4 ${isDarkPreview ? "text-zinc-400" : "text-muted-foreground"}`}>{data.body}</p>
          )}
          {isCarousel && bullets.length > 0 && (
            <ul className="space-y-0.5">
              {bullets.map((b, i) => (
                <li key={i} className={`text-[9px] flex items-start gap-1 ${isDarkPreview ? "text-zinc-400" : "text-muted-foreground"}`}>
                  <span className="text-primary mt-0.5">•</span> {b}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Bottom */}
        <div>
          {(data.cta) && (
            <div className="rounded-md bg-primary/90 text-primary-foreground text-[9px] font-semibold text-center py-1.5 px-2">
              {data.cta}
            </div>
          )}
          {isCarousel && data.role === "cta" && (
            <p className={`text-[8px] text-center mt-1 ${isDarkPreview ? "text-zinc-500" : "text-muted-foreground"}`}>
              {settings.author_name} · {settings.handle}
            </p>
          )}
        </div>
      </div>

      {/* Slide number badge */}
      <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-foreground/80 text-background flex items-center justify-center text-[8px] font-bold" style={{ zIndex: 3 }}>
        {data.n}
      </div>

      {/* Theme indicator badge */}
      {appearance?.theme && appearance.theme !== "auto" && (
        <div className={`absolute top-2 left-2 px-1.5 py-0.5 rounded text-[7px] font-semibold ${
          isDarkPreview ? "bg-zinc-700 text-zinc-200" : "bg-zinc-200 text-zinc-700"
        }`} style={{ zIndex: 3 }}>
          {isDarkPreview ? "🌙" : "☀️"}
        </div>
      )}
    </div>
  );
}
