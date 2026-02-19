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



  return (
    <div
      className={`relative overflow-hidden rounded-lg border bg-card ${
        isCarousel ? "slide-preview-carousel" : "slide-preview-story"
      }`}
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
            background: `linear-gradient(135deg, ${settings.brand_color}22 0%, ${settings.brand_color}08 100%)`,
          }}
        />
      )}

      {/* Content overlay */}
      <div className="relative h-full flex flex-col justify-between p-4 text-foreground">
        {/* Top */}
        <div className="space-y-1.5">
          {isCarousel && data.role === "cover" && (
            <span className="text-[9px] font-semibold uppercase tracking-widest text-primary">
              {settings.handle}
            </span>
          )}
          <h3 className="text-sm font-bold leading-snug line-clamp-3">
            {data.headline}
          </h3>
          {(data.subhead || data.support) && (
            <p className="text-[10px] text-muted-foreground leading-tight line-clamp-2">
              {data.subhead || data.support}
            </p>
          )}
        </div>

        {/* Middle */}
        <div className="flex-1 flex items-center">
          {isCarousel && data.body && (
            <p className="text-[9px] text-muted-foreground leading-relaxed line-clamp-4">{data.body}</p>
          )}
          {isCarousel && bullets.length > 0 && (
            <ul className="space-y-0.5">
              {bullets.map((b, i) => (
                <li key={i} className="text-[9px] text-muted-foreground flex items-start gap-1">
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
            <p className="text-[8px] text-muted-foreground text-center mt-1">
              {settings.author_name} · {settings.handle}
            </p>
          )}
        </div>
      </div>

      {/* Slide number badge */}
      <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-foreground/80 text-background flex items-center justify-center text-[8px] font-bold">
        {data.n}
      </div>
    </div>
  );
}
