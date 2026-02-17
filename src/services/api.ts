import type {
  Project,
  ProjectFormat,
  CarouselOutline,
  StoriesOutline,
  CarouselSlide,
  StoryFrame,
  ToneType,
  AppSettings,
} from "@/types/project";

const API_BASE = "/api";

// ── Storage helpers (mock with localStorage) ──

function getProjects(): Project[] {
  const raw = localStorage.getItem("cf_projects");
  return raw ? JSON.parse(raw) : [];
}

function saveProjects(projects: Project[]) {
  localStorage.setItem("cf_projects", JSON.stringify(projects));
}

function getSettings(): AppSettings {
  const raw = localStorage.getItem("cf_settings");
  return raw
    ? JSON.parse(raw)
    : { author_name: "Seu Nome", handle: "@seuhandle", brand_color: "#2a9d8f" };
}

function saveSettings(s: AppSettings) {
  localStorage.setItem("cf_settings", JSON.stringify(s));
}

// ── Mock data generators ──

function mockCarouselOutline(title: string, count: number): CarouselOutline {
  const slides: CarouselSlide[] = [];
  for (let i = 1; i <= count; i++) {
    const type = i === 1 ? "cover" : i === count ? "cta" : "body";
    slides.push({
      n: i,
      type,
      headline:
        type === "cover"
          ? title
          : type === "cta"
          ? "Gostou? Salve e compartilhe!"
          : `Dica #${i - 1} sobre ${title}`,
      subhead: type === "cover" ? "Deslize para aprender →" : null,
      body:
        type === "body"
          ? `Este é o conteúdo do slide ${i}. Aqui vai uma explicação detalhada sobre o tema abordado.`
          : null,
      bullets: type === "body" && i % 2 === 0 ? ["Ponto 1", "Ponto 2", "Ponto 3"] : [],
      cta: type === "cta" ? "Siga para mais conteúdo!" : null,
      image_brief: `Imagem ilustrativa para slide ${i} sobre ${title}`,
    });
  }
  return { format: "carousel", slides };
}

function mockStoriesOutline(title: string, ctaObj: string): StoriesOutline {
  const frames: StoryFrame[] = [];
  for (let i = 1; i <= 10; i++) {
    frames.push({
      n: i,
      headline:
        i === 1
          ? `Você sabia disso sobre ${title}?`
          : i === 10
          ? "Quer saber mais?"
          : `Insight ${i}: ${title}`,
      support:
        i < 10
          ? `Detalhe complementar para o frame ${i}. Mantenha a atenção do espectador.`
          : null,
      cta: i === 10 ? ctaObj || 'Responde "EU QUERO" no DM' : null,
      image_brief: `Visual para story frame ${i}`,
    });
  }
  return {
    format: "stories_10x",
    frames,
    cta: { action: "DM", trigger_word: "EU QUERO" },
  };
}

// ── API Functions (mock, ready to swap for real fetch calls) ──

export async function fetchProjects(): Promise<Project[]> {
  // Replace with: fetch(`${API_BASE}/projects`)
  await delay(300);
  return getProjects();
}

export async function createProject(data: {
  format: ProjectFormat;
  title: string;
  slide_count?: number;
  tone?: ToneType;
  cta_objective?: string;
}): Promise<Project> {
  await delay(400);
  const project: Project = {
    id: crypto.randomUUID(),
    format: data.format,
    title: data.title,
    status: "draft",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    slide_count: data.slide_count || (data.format === "carousel" ? 8 : 10),
    tone: data.tone,
    cta_objective: data.cta_objective,
    outline: null,
    rendered_slides: [],
  };
  const projects = getProjects();
  projects.unshift(project);
  saveProjects(projects);
  return project;
}

export async function generateOutline(projectId: string): Promise<Project> {
  await delay(1200);
  const projects = getProjects();
  const idx = projects.findIndex((p) => p.id === projectId);
  if (idx === -1) throw new Error("Projeto não encontrado");

  const project = projects[idx];
  if (project.format === "carousel") {
    project.outline = mockCarouselOutline(project.title, project.slide_count || 8);
  } else {
    project.outline = mockStoriesOutline(project.title, project.cta_objective || "");
  }
  project.status = "outline_ready";
  project.updated_at = new Date().toISOString();
  saveProjects(projects);
  return project;
}

export async function renderSlides(projectId: string): Promise<Project> {
  await delay(1500);
  const projects = getProjects();
  const idx = projects.findIndex((p) => p.id === projectId);
  if (idx === -1) throw new Error("Projeto não encontrado");

  const project = projects[idx];
  const count =
    project.format === "carousel"
      ? (project.outline as CarouselOutline)?.slides.length || 8
      : 10;
  project.rendered_slides = Array.from({ length: count }, (_, i) => `slide_${String(i + 1).padStart(2, "0")}.png`);
  project.status = "rendered";
  project.updated_at = new Date().toISOString();
  saveProjects(projects);
  return project;
}

export async function updateSlide(
  projectId: string,
  slideNumber: number,
  data: Partial<CarouselSlide> | Partial<StoryFrame>
): Promise<Project> {
  await delay(300);
  const projects = getProjects();
  const idx = projects.findIndex((p) => p.id === projectId);
  if (idx === -1) throw new Error("Projeto não encontrado");

  const project = projects[idx];
  if (project.outline?.format === "carousel") {
    const sIdx = (project.outline as CarouselOutline).slides.findIndex((s) => s.n === slideNumber);
    if (sIdx !== -1) {
      Object.assign((project.outline as CarouselOutline).slides[sIdx], data);
    }
  } else if (project.outline?.format === "stories_10x") {
    const fIdx = (project.outline as StoriesOutline).frames.findIndex((f) => f.n === slideNumber);
    if (fIdx !== -1) {
      Object.assign((project.outline as StoriesOutline).frames[fIdx], data);
    }
  }
  project.updated_at = new Date().toISOString();
  saveProjects(projects);
  return project;
}

export async function uploadSlideImage(
  projectId: string,
  slideNumber: number,
  file: File
): Promise<string> {
  await delay(500);
  const url = URL.createObjectURL(file);
  const projects = getProjects();
  const idx = projects.findIndex((p) => p.id === projectId);
  if (idx !== -1) {
    const project = projects[idx];
    if (project.outline?.format === "carousel") {
      const slide = (project.outline as CarouselOutline).slides.find((s) => s.n === slideNumber);
      if (slide) slide.image_url = url;
    } else if (project.outline?.format === "stories_10x") {
      const frame = (project.outline as StoriesOutline).frames.find((f) => f.n === slideNumber);
      if (frame) frame.image_url = url;
    }
    saveProjects(projects);
  }
  return url;
}

export async function exportProject(projectId: string): Promise<void> {
  // In real app: window.open(`${API_BASE}/projects/${projectId}/export`)
  await delay(300);
  alert("📦 No ambiente real, o backend geraria um ZIP com os PNGs. Conecte ao FastAPI para ativar.");
}

export async function deleteProject(projectId: string): Promise<void> {
  await delay(200);
  const projects = getProjects().filter((p) => p.id !== projectId);
  saveProjects(projects);
}

export async function fetchSettings(): Promise<AppSettings> {
  await delay(100);
  return getSettings();
}

export async function updateSettings(s: AppSettings): Promise<AppSettings> {
  await delay(200);
  saveSettings(s);
  return s;
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
