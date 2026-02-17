import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchProjects, deleteProject } from "@/services/api";
import type { Project } from "@/types/project";
import ProjectCard from "@/components/ProjectCard";
import { Button } from "@/components/ui/button";
import { Layers, Instagram, Trash2 } from "lucide-react";

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchProjects().then((p) => {
      setProjects(p);
      setLoading(false);
    });
  }, []);

  async function handleDelete(id: string) {
    if (!confirm("Excluir este projeto?")) return;
    await deleteProject(id);
    setProjects((prev) => prev.filter((p) => p.id !== id));
  }

  return (
    <div className="p-6 md:p-10 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-1">Dashboard</h1>
        <p className="text-muted-foreground text-sm">
          Gerencie seus projetos de conteúdo para Instagram
        </p>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3 mb-8">
        <Link to="/create/carousel">
          <Button className="gap-2">
            <Layers className="w-4 h-4" /> Novo Carrossel
          </Button>
        </Link>
        <Link to="/create/stories">
          <Button variant="outline" className="gap-2">
            <Instagram className="w-4 h-4" /> Novo Stories 10x
          </Button>
        </Link>
      </div>

      {/* Project list */}
      {loading ? (
        <div className="text-muted-foreground text-sm">Carregando...</div>
      ) : projects.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          <Layers className="w-12 h-12 mx-auto mb-4 opacity-30" />
          <p className="text-lg font-medium mb-1">Nenhum projeto ainda</p>
          <p className="text-sm">Crie seu primeiro carrossel ou sequência de stories</p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <div key={p.id} className="relative group">
              <ProjectCard project={p} />
              <button
                onClick={(e) => {
                  e.preventDefault();
                  handleDelete(p.id);
                }}
                className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-md bg-destructive/10 hover:bg-destructive/20 text-destructive"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
