import { useState, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchTemplatePreview } from "@/services/api";
import { AlertTriangle, RefreshCw, WifiOff, Eye } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface TemplateCardProps {
  templateId: string;
  label: string;
  format: string;
  role: string;
  family: string;
  cacheKey: number; // increment to bust cache
}

interface PreviewData {
  image_base64: string;
  warnings: string[];
  slot_info: Record<string, any>;
  template_path?: string;
}

export default function TemplateCard({
  templateId,
  label,
  format,
  role,
  family,
  cacheKey,
}: TemplateCardProps) {
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [hasFetched, setHasFetched] = useState(0);

  const loadPreview = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchTemplatePreview(templateId, format);
      setPreview(data);
    } catch (err: any) {
      setError(err.message || "Backend offline");
    } finally {
      setLoading(false);
    }
  }, [templateId, format]);

  // Auto-fetch on mount / cache bust
  if (hasFetched !== cacheKey && !loading) {
    setHasFetched(cacheKey);
    loadPreview();
  }

  const isStory = format === "stories";
  const aspectClass = isStory ? "aspect-[9/16]" : "aspect-[4/5]";

  return (
    <>
      <Card
        className="group cursor-pointer overflow-hidden transition-shadow hover:shadow-lg border-border/50 bg-card"
        onClick={() => preview && setModalOpen(true)}
      >
        <div className={`relative ${aspectClass} bg-muted overflow-hidden`}>
          {loading && (
            <Skeleton className="absolute inset-0 rounded-none" />
          )}
          {error && !loading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-4 text-center">
              <WifiOff className="w-8 h-8 text-muted-foreground/50" />
              <p className="text-xs text-muted-foreground">{error}</p>
              <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); loadPreview(); }}>
                <RefreshCw className="w-3 h-3 mr-1" /> Tentar
              </Button>
            </div>
          )}
          {preview && !loading && (
            <img
              src={`data:image/png;base64,${preview.image_base64}`}
              alt={label}
              className="w-full h-full object-cover"
            />
          )}
          {/* Hover overlay */}
          {preview && (
            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
              <Eye className="w-6 h-6 text-white" />
            </div>
          )}
        </div>
        <CardContent className="p-3 space-y-1">
          <p className="text-sm font-medium truncate">{label}</p>
          <div className="flex items-center gap-1.5 flex-wrap">
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
              {templateId}
            </Badge>
            <Badge variant="outline" className="text-[10px] px-1.5 py-0">
              {role}
            </Badge>
          </div>
          {preview?.warnings && preview.warnings.length > 0 && (
            <div className="flex items-center gap-1 mt-1">
              <AlertTriangle className="w-3 h-3 text-yellow-500" />
              <span className="text-[10px] text-yellow-600">
                {preview.warnings.length} warning{preview.warnings.length > 1 ? "s" : ""}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detail Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{label}</DialogTitle>
          </DialogHeader>
          {preview && (
            <div className="space-y-4">
              <div className={`${isStory ? "max-w-xs" : "max-w-md"} mx-auto`}>
                <img
                  src={`data:image/png;base64,${preview.image_base64}`}
                  alt={label}
                  className="w-full rounded-lg border"
                />
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div><span className="text-muted-foreground">Template ID:</span> <code className="text-xs">{templateId}</code></div>
                <div><span className="text-muted-foreground">Family:</span> {family}</div>
                <div><span className="text-muted-foreground">Format:</span> {format}</div>
                <div><span className="text-muted-foreground">Role:</span> {role}</div>
                {preview.template_path && (
                  <div className="col-span-2"><span className="text-muted-foreground">Path:</span> <code className="text-xs">{preview.template_path}</code></div>
                )}
              </div>
              {preview.slot_info && Object.keys(preview.slot_info).length > 0 && (
                <div>
                  <p className="text-sm font-medium mb-1">Slots</p>
                  <pre className="text-xs bg-muted p-2 rounded overflow-x-auto">
                    {JSON.stringify(preview.slot_info, null, 2)}
                  </pre>
                </div>
              )}
              {preview.warnings.length > 0 && (
                <div>
                  <p className="text-sm font-medium mb-1 text-yellow-600">Warnings</p>
                  <ul className="text-xs space-y-0.5">
                    {preview.warnings.map((w, i) => (
                      <li key={i} className="flex items-start gap-1">
                        <AlertTriangle className="w-3 h-3 text-yellow-500 mt-0.5 shrink-0" />
                        {w}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
