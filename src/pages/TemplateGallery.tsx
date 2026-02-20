import { useEffect, useState, useCallback } from "react";
import { fetchTemplateRegistry } from "@/services/api";
import TemplateCard from "@/components/TemplateCard";
import { Button } from "@/components/ui/button";
import { RefreshCw, Loader2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

interface TemplateEntry {
  id: string;
  label: string;
  file: string;
}

interface ParsedTemplate {
  id: string;
  label: string;
  role: string;
  format: string;
  family: string;
}

function parseRegistry(registry: Record<string, any>): Record<string, ParsedTemplate[]> {
  const grouped: Record<string, ParsedTemplate[]> = {};

  for (const [topKey, topValue] of Object.entries(registry)) {
    // Check if this is a family (has nested format keys like carousel/stories)
    const isFamily = topValue && typeof topValue === "object" &&
      Object.values(topValue).some((v: any) => typeof v === "object" && !Array.isArray(v) && !v.id);

    if (isFamily) {
      // Family like premium_editorial_v1: { carousel: { cover: [...], body: [...] }, stories: { frame: [...] } }
      const familyName = topKey;
      for (const [formatKey, roles] of Object.entries(topValue as Record<string, any>)) {
        for (const [roleKey, templates] of Object.entries(roles as Record<string, any>)) {
          if (!Array.isArray(templates)) continue;
          const sectionKey = `${familyName}`;
          if (!grouped[sectionKey]) grouped[sectionKey] = [];
          for (const t of templates as TemplateEntry[]) {
            grouped[sectionKey].push({
              id: t.id,
              label: t.label,
              role: roleKey,
              format: formatKey,
              family: familyName,
            });
          }
        }
      }
    } else {
      // Legacy: carousel: { cover: [...], body: [...] }  or stories: { frame: [...] }
      const formatKey = topKey;
      for (const [roleKey, templates] of Object.entries(topValue as Record<string, any>)) {
        if (!Array.isArray(templates)) continue;
        const sectionKey = "classic";
        if (!grouped[sectionKey]) grouped[sectionKey] = [];
        for (const t of templates as TemplateEntry[]) {
          grouped[sectionKey].push({
            id: t.id,
            label: t.label,
            role: roleKey,
            format: formatKey,
            family: "classic",
          });
        }
      }
    }
  }

  return grouped;
}

const FAMILY_LABELS: Record<string, string> = {
  classic: "Classic (Legacy)",
  premium_editorial_v1: "Premium Editorial V1",
};

export default function TemplateGallery() {
  const [registry, setRegistry] = useState<Record<string, ParsedTemplate[]> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cacheKey, setCacheKey] = useState(1);

  const loadRegistry = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchTemplateRegistry();
      setRegistry(parseRegistry(data));
    } catch (err: any) {
      setError(err.message || "Falha ao carregar registry");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRegistry();
  }, [loadRegistry]);

  const handleRegenerate = () => {
    setCacheKey((k) => k + 1);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Template Gallery</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Previews gerados via Playwright — o que você vê é o que o render produz.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleRegenerate}>
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          Regerar thumbnails
        </Button>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          Carregando registry...
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center space-y-2">
          <p className="text-sm text-destructive">{error}</p>
          <Button size="sm" variant="outline" onClick={loadRegistry}>
            <RefreshCw className="w-3 h-3 mr-1" /> Tentar novamente
          </Button>
        </div>
      )}

      {/* Gallery sections */}
      {registry && Object.entries(registry).map(([familyKey, templates]) => {
        // Group by role
        const byRole: Record<string, ParsedTemplate[]> = {};
        for (const t of templates) {
          if (!byRole[t.role]) byRole[t.role] = [];
          byRole[t.role].push(t);
        }

        return (
          <section key={familyKey} className="space-y-6">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-primary/80 border-b border-border pb-2">
              {FAMILY_LABELS[familyKey] || familyKey}
            </h2>

            {Object.entries(byRole).map(([roleKey, roleTemplates]) => (
              <div key={roleKey} className="space-y-3">
                <h3 className="text-sm font-medium text-muted-foreground capitalize">
                  {roleKey} <span className="text-muted-foreground/50">· {roleTemplates[0]?.format}</span>
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                  {roleTemplates.map((t) => (
                    <TemplateCard
                      key={`${t.id}-${cacheKey}`}
                      templateId={t.id}
                      label={t.label}
                      format={t.format}
                      role={t.role}
                      family={t.family}
                      cacheKey={cacheKey}
                    />
                  ))}
                </div>
              </div>
            ))}
          </section>
        );
      })}
    </div>
  );
}
