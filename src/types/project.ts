export type ProjectType = "carousel" | "stories_10x";
export type SlideRole = "cover" | "body" | "cta" | "frame" | "frame_cta";
export type ToneType = "soft" | "medium" | "direct";
export type ProjectStatus = "draft" | "outlined" | "rendering" | "rendered";

export interface SlideAppearance {
  theme: "auto" | "light" | "dark";
  scrim: {
    enabled: boolean;
    strength: number;
    position: "top" | "center" | "bottom";
    mode: "gradient" | "box";
  };
}

// Raw slide from backend
export interface Slide {
  id: string;
  project_id: string;
  index: number;
  role: SlideRole;
  payload: Record<string, any>;
  image_path: string | null;
  render_path: string | null;
}

// Enriched slide for frontend UI
export interface UiSlide {
  n: number;
  role: SlideRole;
  // Common fields
  headline: string;
  image_path: string | null;
  render_path: string | null;
  // Carousel-specific
  subhead?: string;
  body?: string;
  bullets?: string[];
  cta?: string;
  subcta?: string;
  // Story-specific
  support?: string;
  kicker?: string;
  progress?: string;
  trigger_word?: string;
  // Appearance overrides
  appearance?: SlideAppearance;
}

export interface Project {
  id: string;
  type: ProjectType;
  title: string;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
  slides_count?: number;
  template_selection?: Record<string, any>;
  rendered_at?: string;
  render_version?: string;
  slides?: UiSlide[];
}

export interface TemplateSelection {
  family: string;
  carousel?: {
    cover?: string;
    body?: string;
    cta?: string;
  };
  stories?: {
    frame?: string;
    cta?: string;
  };
}

export interface AppSettings {
  author_name: string;
  handle: string;
  brand_color: string;
}
