import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  fetchProjectWithSlides,
  generateOutline,
  renderSlides,
  updateSlide,
  uploadSlideImage,
  exportProject,
} from "@/services/api";
import { fetchSettings } from "@/services/api";
import type { Project, UiSlide, AppSettings } from "@/types/project";
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
    Promise.all([fetchProjectWithSlides(id!), fetchSettings()]).then(([p, s]) => {
      setProject(p);
      setSettings(s);
    });
  }, [id]);

  if (!project) {
    return (
      <div className="p-10 text-center text-muted-foreground">Carregando projeto...</div>
    );
  }

  const isCarousel = project.type === "carousel";
  const slides = project.slides || [];

  async function handleGenerateOutline() {
    setLoading("outline");
    await generateOutline(project!.id, { topic: project!.title });
    const refreshed = await fetchProjectWithSlides(project!.id);
    setProject(refreshed);
    setLoading("");
  }

  async function handleRender() {
    setLoading("render");
    try {
      const result = await renderSlides(project!.id);
      if (result.failed > 0) {
        const failedInfo = result.failed_slides?.map(
          (s) => `Slide ${s.index}: ${s.error_code} — ${s.error_message}`
        ).join("\n") || "Detalhes indisponíveis";
        alert(`⚠ Render parcial: ${result.failed}/${result.total} slides falharam.\n\n${failedInfo}`);
      }
    } catch (err: any) {
      alert(`Erro no render: ${err.message}`);
    }
    const refreshed = await fetchProjectWithSlides(project!.id);
    setProject(refreshed);
    setLoading("");
  }

  async function handleExport() {
    setLoading("export");
    await exportProject(project!.id);
    setLoading("");
  }

  async function handleSaveSlide(slideN: number, data: Partial<UiSlide>) {
    const updatedSlide = await updateSlide(project!.id, slideN, data);
    setProject((prev) => prev ? { ...prev, slides: prev.slides?.map((s) => (s.n === slideN ? updatedSlide : s)) } : prev);
    setEditingSlide(null);
  }

  async function handleUploadImage(slideN: number, file: File) {
    const updatedSlide = await uploadSlideImage(project!.id, slideN, file);
    setProject((prev) => prev ? { ...prev, slides: prev.slides?.map((s) => (s.n === slideN ? updatedSlide : s)) } : prev);
    // Refresh project
    
  }

  const statusLabels: Record<string, string> = {
    draft: "Rascunho",
    outlined: "Roteiro pronto",
    rendering: "Renderizando",
    rendered: "Renderizado",
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
          {(project.status === "outlined" || project.status === "rendered") && (
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
        <>
          <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 mb-4">
            {slides.map((s) => (
              <div
                key={s.n}
                className="cursor-pointer hover:ring-2 hover:ring-primary/40 rounded-lg transition-all"
                onClick={() => setEditingSlide(s.n)}
              >
                <SlidePreview format={project.type} data={s} settings={settings} />
              </div>
            ))}
          </div>
          {slides.some((s) => !s.render_path && s.headline) && (
            <p className="text-xs text-amber-600 mb-8">
              ⚠ Slides editados desde a última renderização. Clique em "Renderizar PNGs" para atualizar.
            </p>
          )}
        </>
      )}

      {/* Slide editor */}
      {editingSlide !== null && (
        <SlideEditor
          format={project.type}
          data={slides.find((s) => s.n === editingSlide)!}
          familyName={project.template_selection?.family as string | undefined}
          onSave={(data) => handleSaveSlide(editingSlide, data)}
          onUploadImage={(file) => handleUploadImage(editingSlide, file)}
          onClose={() => setEditingSlide(null)}
        />
      )}
    </div>
  );
}
