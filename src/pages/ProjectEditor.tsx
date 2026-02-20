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
import { toast } from "sonner";
import { ArrowLeft, Sparkles, Image, Download, Loader2, RefreshCw } from "lucide-react";

export default function ProjectEditor() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [settings, setSettings] = useState<AppSettings>({ author_name: "", handle: "", brand_color: "#2a9d8f" });
  const [editingSlide, setEditingSlide] = useState<number | null>(null);
  const [loading, setLoading] = useState("");
  const [renderWarnings, setRenderWarnings] = useState<Array<{ index: number; warnings: string[] }>>([]);

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
    setRenderWarnings([]);
    try {
      const result = await renderSlides(project!.id);

      // Collect warnings (not errors)
      const slideWarnings = result.slides
        .filter((s) => s.ok && s.warnings && s.warnings.length > 0)
        .map((s) => ({ index: s.index, warnings: s.warnings! }));
      setRenderWarnings(slideWarnings);

      // Collect actual failures
      const failures = result.slides.filter((s) => !s.ok);

      if (failures.length > 0) {
        const failedInfo = failures.map(
          (s) => `Slide ${s.index}: ${s.error_code} — ${s.error_message}`
        ).join("\n");
        toast.error(`${failures.length}/${result.total} slides falharam no render.`);
        alert(`⚠ Render parcial: ${failures.length}/${result.total} slides falharam.\n\n${failedInfo}`);
      } else if (slideWarnings.length > 0) {
        toast.success(`Render concluído com ${slideWarnings.length} aviso(s).`);
      } else {
        toast.success("Todos os slides renderizados com sucesso!");
      }
    } catch (err: any) {
      toast.error(`Erro no render: ${err.message}`);
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
    try {
      const updatedSlide = await updateSlide(project!.id, slideN, data);
      setProject((prev) => prev ? { ...prev, slides: prev.slides?.map((s) => (s.n === slideN ? updatedSlide : s)) } : prev);
      setEditingSlide(null);
    } catch (err: any) {
      toast.error(`Erro ao salvar: ${err.message}`);
    }
  }

  async function handleUploadImage(slideN: number, file: File) {
    try {
      const updatedSlide = await uploadSlideImage(project!.id, slideN, file);
      setProject((prev) => prev ? { ...prev, slides: prev.slides?.map((s) => (s.n === slideN ? updatedSlide : s)) } : prev);
      toast.success("Imagem enviada! Renderize para ver o resultado.");
    } catch (err: any) {
      if (err.message.includes("413") || err.message.includes("10MB")) {
        toast.error("Imagem excede o limite de 10MB.");
      } else {
        toast.error(`Erro no upload: ${err.message}`);
      }
    }
  }

  const statusLabels: Record<string, string> = {
    draft: "Rascunho",
    outlined: "Roteiro pronto",
    rendering: "Renderizando",
    rendered: "Renderizado",
  };

  const hasStaleSlides = slides.some((s) => !s.render_path && s.headline);

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

          {/* Stale slides warning */}
          {hasStaleSlides && (
            <div className="flex items-center gap-2 text-xs text-amber-600 mb-4">
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Slides editados desde a última renderização. Clique em "Renderizar PNGs" para atualizar.</span>
            </div>
          )}

          {/* Render warnings */}
          {renderWarnings.length > 0 && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 mb-4 space-y-1">
              <p className="text-xs font-semibold text-amber-600">Avisos do render:</p>
              {renderWarnings.map((rw) => (
                <p key={rw.index} className="text-[11px] text-amber-600">
                  Slide {rw.index}: {rw.warnings.join(", ")}
                </p>
              ))}
            </div>
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
