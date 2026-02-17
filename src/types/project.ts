export type ProjectFormat = "carousel" | "stories_10x";
export type SlideType = "cover" | "body" | "cta";
export type ToneType = "soft" | "medium" | "direct";
export type ProjectStatus = "draft" | "outline_ready" | "rendered" | "exported";

export interface CarouselSlide {
  n: number;
  type: SlideType;
  headline: string;
  subhead?: string | null;
  body?: string | null;
  bullets: string[];
  cta?: string | null;
  image_brief?: string | null;
  image_url?: string | null;
}

export interface StoryFrame {
  n: number;
  headline: string;
  support?: string | null;
  cta?: string | null;
  image_brief?: string | null;
  image_url?: string | null;
}

export interface CarouselOutline {
  format: "carousel";
  slides: CarouselSlide[];
}

export interface StoriesOutline {
  format: "stories_10x";
  frames: StoryFrame[];
  cta: {
    action: string;
    trigger_word: string;
  };
}

export interface Project {
  id: string;
  format: ProjectFormat;
  title: string;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
  slide_count?: number;
  tone?: ToneType;
  cta_objective?: string;
  outline?: CarouselOutline | StoriesOutline | null;
  rendered_slides?: string[];
}

export interface AppSettings {
  author_name: string;
  handle: string;
  brand_color: string;
}
