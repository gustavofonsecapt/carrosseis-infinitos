import { useState, useRef } from "react";
import type { CarouselSlide, StoryFrame } from "@/types/project";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Upload, Save, X } from "lucide-react";

interface SlideEditorProps {
  format: "carousel" | "stories_10x";
  data: CarouselSlide | StoryFrame;
  onSave: (data: Partial<CarouselSlide> | Partial<StoryFrame>) => void;
  onUploadImage: (file: File) => void;
  onClose: () => void;
}

export default function SlideEditor({ format, data, onSave, onUploadImage, onClose }: SlideEditorProps) {
  const isCarousel = format === "carousel";
  const slide = data as CarouselSlide;
  const frame = data as StoryFrame;
  const fileRef = useRef<HTMLInputElement>(null);

  const [headline, setHeadline] = useState(data.headline || "");
  const [subhead, setSubhead] = useState(isCarousel ? slide.subhead || "" : frame.support || "");
  const [body, setBody] = useState(isCarousel ? slide.body || "" : "");
  const [bullets, setBullets] = useState(isCarousel ? slide.bullets?.join("\n") || "" : "");
  const [cta, setCta] = useState((isCarousel ? slide.cta : frame.cta) || "");

  function handleSave() {
    if (isCarousel) {
      onSave({
        headline,
        subhead: subhead || null,
        body: body || null,
        bullets: bullets ? bullets.split("\n").filter(Boolean) : [],
        cta: cta || null,
      });
    } else {
      onSave({
        headline,
        support: subhead || null,
        cta: cta || null,
      });
    }
  }

  return (
    <div className="bg-card border rounded-xl p-6 space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">
          Editando {isCarousel ? "Slide" : "Frame"} {data.n}
          {isCarousel && (
            <span className="ml-2 text-xs text-muted-foreground capitalize">({slide.type})</span>
          )}
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

        {isCarousel && slide.type === "body" && (
          <>
            <div>
              <Label className="text-xs">Corpo do texto</Label>
              <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} />
            </div>
            <div>
              <Label className="text-xs">Bullets (um por linha)</Label>
              <Textarea value={bullets} onChange={(e) => setBullets(e.target.value)} rows={3} placeholder={"Ponto 1\nPonto 2\nPonto 3"} />
            </div>
          </>
        )}

        {(isCarousel ? slide.type === "cta" : data.n === 10) && (
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
        <Button
          variant="outline"
          className="gap-2"
          onClick={() => fileRef.current?.click()}
        >
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
