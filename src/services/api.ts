import type {
  Project,
  ProjectType,
  ToneType,
  UiSlide,
  Slide as ApiSlide,
  AppSettings,
  TemplateSelection,
  SlideAppearance,
} from "@/types/project";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8100";

// ── HTTP Helper ──
async function http<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!resp.ok) {
    const errorBody = await resp.json().catch(() => ({}));
    const message = errorBody.error?.message || `HTTP Error ${resp.status}`;
    throw new Error(message);
  }
  return resp.json();
}

// ── Mappers ──
function mapApiSlideToUiSlide(apiSlide: ApiSlide): UiSlide {
  const p = apiSlide.payload || {};
  const first = (...keys: string[]) => keys.map((k) => p[k]).find((v) => v !== undefined && v !== null && (!(typeof v === "string") || v.trim() !== ""));

  return {
    n: apiSlide.index,
    role: apiSlide.role,
    payload: p,
    headline: (first("headline", "title", "cta_title", "h1", "heading") as string) || "",
    image_path: apiSlide.image_path,
    render_path: apiSlide.render_path,
    subhead: (first("subhead", "subtitle", "support", "kicker", "description") as string) || undefined,
    body: (first("body", "text", "content", "paragraph") as string) || undefined,
    bullets: Array.isArray(p.bullets) ? p.bullets : Array.isArray(p.list) ? p.list : undefined,
    cta: (first("cta", "cta_button", "button") as string) || undefined,
    subcta: p.subcta,
    support: p.support,
    kicker: p.kicker,
    progress: p.progress,
    trigger_word: p.trigger_word,
    appearance: (p.appearance || apiSlide.payload?.appearance) || undefined,
    template_variant: p.template_variant || undefined,
  };
}

// ── Projects API ──
export async function fetchProjects(): Promise<Project[]> {
  const { items } = await http<{ items: Project[] }>("/api/projects");
  return items;
}

export async function fetchProjectWithSlides(id: string): Promise<Project> {
  const [project, slides] = await Promise.all([
    http<Project>(`/api/projects/${id}`),
    http<ApiSlide[]>(`/api/projects/${id}/slides`),
  ]);
  return { ...project, slides: slides.map(mapApiSlideToUiSlide) };
}

export async function createProject(data: {
  type: ProjectType;
  title: string;
  slides_count: number;
  template_selection?: TemplateSelection;
}): Promise<Project> {
  return http<Project>("/api/projects", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteProject(projectId: string): Promise<void> {
  await fetch(`${API_BASE}/api/projects/${projectId}`, { method: "DELETE" });
}

// ── Actions API ──
export async function generateOutline(
  projectId: string,
  payload: { topic: string; tone?: ToneType; cta_action?: string, cta_trigger_word?: string }
): Promise<Project> {
  return http<Project>(`/api/projects/${projectId}/generate-outline`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface RenderResult {
  status: "ok" | "partial_failure";
  project_id: string;
  total: number;
  failed: number;
  slides: Array<{
    index: number;
    ok: boolean;
    render_path?: string;
    template_id?: string;
    warnings?: string[];
    error_code?: string;
    error_message?: string;
  }>;
  failed_slides?: Array<{
    index: number;
    ok: boolean;
    error_code?: string;
    error_message?: string;
  }>;
  template_selection?: Record<string, any>;
}

export async function renderSlides(projectId: string, debug = false): Promise<RenderResult> {
  const url = debug
    ? `/api/projects/${projectId}/render?debug=1`
    : `/api/projects/${projectId}/render`;
  const resp = await fetch(`${API_BASE}${url}`, { method: "POST" });
  if (!resp.ok && resp.status !== 207) {
    const errorBody = await resp.json().catch(() => ({}));
    const message = errorBody.error?.message || `HTTP Error ${resp.status}`;
    throw new Error(message);
  }
  return resp.json();
}

export async function exportProject(projectId: string): Promise<void> {
  window.open(`${API_BASE}/api/projects/${projectId}/export`);
}

// ── Slides API ──
export async function updateSlide(
  projectId: string,
  slideN: number,
  payload: Record<string, any>
): Promise<UiSlide> {
  const updated = await http<ApiSlide>(`/api/projects/${projectId}/slides/${slideN}`, {
    method: "PATCH",
    body: JSON.stringify({ payload }),
  });
  return mapApiSlideToUiSlide(updated);
}

export async function uploadSlideImage(
  projectId: string,
  slideN: number,
  file: File
): Promise<UiSlide> {
  const formData = new FormData();
  formData.append("file", file);
  const updated = await http<ApiSlide>(`/api/projects/${projectId}/slides/${slideN}/image`, {
    method: "POST",
    body: formData,
  });
  return mapApiSlideToUiSlide(updated);
}

// ── Templates API ──
export async function fetchTemplateRegistry(): Promise<Record<string, any>> {
  return http<Record<string, any>>("/api/templates");
}

export async function fetchTemplatePreview(
  templateId: string,
  formatKey: string = "carousel"
): Promise<{
  image_base64: string;
  warnings: string[];
  slot_info: Record<string, any>;
  template_path?: string;
}> {
  return http("/api/templates/" + templateId + "/preview/json?format_key=" + formatKey, {
    method: "POST",
    body: JSON.stringify(null),
  });
}

// ── Settings (localStorage) ──
export async function fetchSettings(): Promise<AppSettings> {
  const raw = localStorage.getItem("cf_settings");
  return raw
    ? JSON.parse(raw)
    : { author_name: "Seu Nome", handle: "@seuhandle", brand_color: "#2a9d8f" };
}

export async function updateSettings(s: AppSettings): Promise<AppSettings> {
  localStorage.setItem("cf_settings", JSON.stringify(s));
  return s;
}
