import { Link } from "react-router-dom";
import type { Project } from "@/types/project";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Layers, Instagram, Clock } from "lucide-react";

const statusLabels: Record<string, string> = {
  draft: "Rascunho",
  outline_ready: "Roteiro pronto",
  rendered: "Renderizado",
  exported: "Exportado",
};

const statusColors: Record<string, string> = {
  draft: "bg-muted text-muted-foreground",
  outline_ready: "bg-primary/10 text-primary",
  rendered: "bg-success/10 text-success",
  exported: "bg-accent/10 text-accent",
};

export default function ProjectCard({ project }: { project: Project }) {
  const isCarousel = project.format === "carousel";

  return (
    <Link to={`/project/${project.id}`}>
      <Card className="group hover:shadow-md transition-all duration-200 hover:border-primary/30 cursor-pointer animate-fade-in">
        <CardContent className="p-5">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${isCarousel ? "bg-primary/10" : "bg-accent/10"}`}>
                {isCarousel ? (
                  <Layers className="w-4 h-4 text-primary" />
                ) : (
                  <Instagram className="w-4 h-4 text-accent" />
                )}
              </div>
              <div>
                <p className="font-semibold text-sm group-hover:text-primary transition-colors">
                  {project.title}
                </p>
                <p className="text-xs text-muted-foreground">
                  {isCarousel ? `Carrossel · ${project.slide_count || 8} slides` : "Stories 10x · 10 frames"}
                </p>
              </div>
            </div>
            <Badge variant="secondary" className={statusColors[project.status]}>
              {statusLabels[project.status]}
            </Badge>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="w-3 h-3" />
            {new Date(project.updated_at).toLocaleDateString("pt-BR")}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
