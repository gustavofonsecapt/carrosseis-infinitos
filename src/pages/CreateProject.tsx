import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { createProject } from "@/services/api";
import type { ProjectType, ToneType } from "@/types/project";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ArrowLeft, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

export default function CreateProject() {
  const { type } = useParams<{ type: string }>();
  const navigate = useNavigate();
  const format: ProjectType = type === "stories" ? "stories_10x" : "carousel";
  const isCarousel = format === "carousel";

  const [title, setTitle] = useState("");
  const [slideCount, setSlideCount] = useState(8);
  const [tone, setTone] = useState<ToneType>("medium");
  const [ctaObjective, setCtaObjective] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleCreate() {
    if (!title.trim()) return;
    setLoading(true);
    const project = await createProject({
      type: format,
      title: title.trim(),
      slides_count: isCarousel ? slideCount : 10,
    });
    navigate(`/project/${project.id}`);
  }

  return (
    <div className="p-6 md:p-10 max-w-lg mx-auto">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6">
        <ArrowLeft className="w-4 h-4" /> Voltar
      </Link>

      <h1 className="text-2xl font-bold mb-1">
        {isCarousel ? "Novo Carrossel" : "Novo Stories 10x"}
      </h1>
      <p className="text-sm text-muted-foreground mb-8">
        Preencha os dados e gere o roteiro automaticamente
      </p>

      <div className="space-y-5">
        <div>
          <Label>Título / Tema</Label>
          <Input
            placeholder={isCarousel ? "Ex.: 5 erros de quem começa a investir" : "Ex.: Como montar um funil de vendas"}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        {isCarousel && (
          <div>
            <Label>Quantidade de slides</Label>
            <Select value={String(slideCount)} onValueChange={(v) => setSlideCount(Number(v))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[5, 6, 7, 8, 9, 10].map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n} slides
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        <div>
          <Label>Tom</Label>
          <Select value={tone} onValueChange={(v) => setTone(v as ToneType)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="soft">Soft — leve e amigável</SelectItem>
              <SelectItem value="medium">Médio — equilibrado</SelectItem>
              <SelectItem value="direct">Direto — assertivo e urgente</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {!isCarousel && (
          <div>
            <Label>Objetivo do CTA</Label>
            <Input
              placeholder='Ex.: Responde "CASA" no DM'
              value={ctaObjective}
              onChange={(e) => setCtaObjective(e.target.value)}
            />
          </div>
        )}

        <Button onClick={handleCreate} disabled={!title.trim() || loading} className="w-full gap-2">
          <Sparkles className="w-4 h-4" />
          {loading ? "Criando..." : "Criar projeto"}
        </Button>
      </div>
    </div>
  );
}
