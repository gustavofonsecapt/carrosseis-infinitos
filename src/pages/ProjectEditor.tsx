import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  fetchProjects,
  generateOutline,
  renderSlides,
  updateSlide,
  uploadSlideImage,
  exportProject,
} from "@/services/api";
import { fetchSettings } from "@/services/api";
import type { Project, CarouselOutline, StoriesOutline, CarouselSlide, StoryFrame, AppSettings } from "@/types/project";
import SlidePreview from "@/components/SlidePreview";
import SlideEditor from "@/components/SlideEditor";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Sparkles, Image, Download, Loader2 } from "lucide-react";

export default function ProjectEditor() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [settings, setSettings] = useState<AppSettings>({ author_name: "", handle: "", brand_color: "#2a9d8f" });
  const [editingSlide, setEditingSlide] = useState<number | null>(null);
  const [loading, setLoading] = useState("");

  useEffect(() => {
    Promise.all([fetchProjects(), fetchSettings()]).then(([projects, s]) => {
      const found = projects.find((p) => p.id === id);
      if (found) setProject(found);
      setSettings(s);
    });
  }, [id]);

  if (!project) {
    return (
      <div className="p-10 text-center text-muted-foreground">Carregando projeto...</div>
    );
  }

  const isCarousel = project.format === "carousel";
  const slides: (CarouselSlide | StoryFrame)[] = isCarousel
    ? (project.outline as CarouselOutline)?.slides || []
    : (project.outline as StoriesOutline)?.frames || [];

  async function handleGenerateOutline() {
    setLoading("outline");
    const updated = await generateOutline(project!.id);
    setProject(updated);
    setLoading("");
  }

  async function handleRender() {
    setLoading("render");
    const updated = await renderSlides(project!.id);
    setProject(updated);
    setLoading("");
  }

  async function handleExport() {
    setLoading("export");
    await exportProject(project!.id);
    setLoading("");
  }

  async function handleSaveSlide(slideN: number, data: Partial<CarouselSlide> | Partial<StoryFrame>) {
    const updated = await updateSlide(project!.id, slideN, data);
    setProject(updated);
    setEditingSlide(null);
  }

  async function handleUploadImage(slideN: number, file: File) {
    await uploadSlideImage(project!.id, slideN, file);
    // Refresh project
    const projects = await fetchProjects();
    const updated = projects.find((p) => p.id === project!.id);
    if (updated) setProject(updated);
  }

  const statusLabels: Record<string, string> = {
    draft: "Rascunho",
    outline_ready: "Roteiro pronto",
    rendered: "Renderizado",
    exported: "Exportado",
  };

  return (
    <div className="p-6 md:p-10 max-w-6xl mx-auto">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6">
        <ArrowLeft className="w-4 h-4" /> Dashboard
      </Link>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold mb-1">{project.title}</h1>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>{isCarousel ? "Carrossel" : "Stories 10x"}</span>
            <span>·</span>
            <Badge variant="secondary">{statusLabels[project.status]}</Badge>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {project.status === "draft" && (
            <Button onClick={handleGenerateOutline} disabled={!!loading} className="gap-2">
              {loading === "outline" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              Gerar roteiro
            </Button>
          )}
          {(project.status === "outline_ready" || project.status === "rendered") && (
            <>
              <Button onClick={handleGenerateOutline} variant="outline" disabled={!!loading} className="gap-2">
                {loading === "outline" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                Regerar roteiro
              </Button>
              <Button onClick={handleRender} disabled={!!loading} className="gap-2">
                {loading === "render" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Image className="w-4 h-4" />}
                Renderizar PNGs
              </Button>
            </>
          )}
          {project.status === "rendered" && (
            <Button onClick={handleExport} variant="outline" disabled={!!loading} className="gap-2">
              {loading === "export" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              Exportar ZIP
            </Button>
          )}
        </div>
      </div>

      {/* Empty state */}
      {slides.length === 0 && (
        <div className="text-center py-20 text-muted-foreground">
          <Sparkles className="w-12 h-12 mx-auto mb-4 opacity-30" />
          <p className="text-lg font-medium mb-1">Projeto criado</p>
          <p className="text-sm">Clique em "Gerar roteiro" para começar</p>
        </div>
      )}

      {/* Slides grid */}
      {slides.length > 0 && (
        <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 mb-8">
          {slides.map((s) => (
            <div
              key={s.n}
              className="cursor-pointer hover:ring-2 hover:ring-primary/40 rounded-lg transition-all"
              onClick={() => setEditingSlide(s.n)}
            >
              <SlidePreview format={project.format} data={s} settings={settings} />
            </div>
          ))}
        </div>
      )}

      {/* Slide editor */}
      {editingSlide !== null && (
        <SlideEditor
          format={project.format}
          data={slides.find((s) => s.n === editingSlide)!}
          onSave={(data) => handleSaveSlide(editingSlide, data)}
          onUploadImage={(file) => handleUploadImage(editingSlide, file)}
          onClose={() => setEditingSlide(null)}
        />
      )}
    </div>
  );
}
