import { useState, useRef } from "react";
import type { UiSlide } from "@/types/project";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Upload, Save, X } from "lucide-react";

interface SlideEditorProps {
  format: "carousel" | "stories_10x";
  data: UiSlide;
  onSave: (payload: Record<string, any>) => void;
  onUploadImage: (file: File) => void;
  onClose: () => void;
}

export default function SlideEditor({ format, data, onSave, onUploadImage, onClose }: SlideEditorProps) {
  const isCarousel = format === "carousel";
  const fileRef = useRef<HTMLInputElement>(null);

  const [headline, setHeadline] = useState(data.headline || "");
  const [subhead, setSubhead] = useState(data.subhead || data.support || "");
  const [body, setBody] = useState(data.body || "");
  const [bullets, setBullets] = useState((data.bullets || []).join("\\n"));
  const [cta, setCta] = useState(data.cta || "");

  function handleSave() {
    const payload: Record<string, any> = {
      headline,
      subhead: subhead || null,
      support: subhead || null,
    };

    if (isCarousel) {
      payload.body = body || null;
      payload.bullets = bullets ? bullets.split("\\n").filter(Boolean) : [];
    }

    if (data.role === "cta" || data.role === "frame_cta") {
      payload.cta = cta || null;
    }

    onSave(payload);
    onClose();
  }

  return (
    <div className="bg-card border rounded-xl p-6 space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">
          Editando {isCarousel ? "Slide" : "Frame"} {data.n}
          <span className="ml-2 text-xs text-muted-foreground capitalize">({data.role})</span>
        </h3>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="w-4 h-4" />
        </Button>
      </div>

      <div className="grid gap-3">
        <div>
          <Label className="text-xs">Headline</Label>
          <Input value={headline} onChange={(e) => setHeadline(e.target.value)} />
        </div>

        <div>
          <Label className="text-xs">{isCarousel ? "Subtítulo" : "Texto de suporte"}</Label>
          <Input value={subhead} onChange={(e) => setSubhead(e.target.value)} />
        </div>

        {isCarousel && data.role === "body" && (
          <>
            <div>
              <Label className="text-xs">Corpo do texto</Label>
              <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} />
            </div>
            <div>
              <Label className="text-xs">Bullets (um por linha)</Label>
              <Textarea value={bullets} onChange={(e) => setBullets(e.target.value)} rows={3} placeholder={`Ponto 1
Ponto 2
Ponto 3`} />
            </div>
          </>
        )}

        {(data.role === "cta" || data.role === "frame_cta") && (
          <div>
            <Label className="text-xs">CTA</Label>
            <Input value={cta} onChange={(e) => setCta(e.target.value)} />
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <Button onClick={handleSave} className="gap-2">
          <Save className="w-4 h-4" /> Salvar
        </Button>
        <Button variant="outline" className="gap-2" onClick={() => fileRef.current?.click()}>
          <Upload className="w-4 h-4" /> Upload imagem
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onUploadImage(file);
          }}
        />
      </div>
    </div>
  );
}
