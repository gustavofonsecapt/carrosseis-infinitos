import { useState, useRef } from "react";
import type { UiSlide, SlideAppearance } from "@/types/project";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Upload, Save, X, Sun, Moon, Monitor } from "lucide-react";
import { Separator } from "@/components/ui/separator";

interface SlideEditorProps {
  format: "carousel" | "stories_10x";
  data: UiSlide;
  onSave: (payload: Record<string, any>) => void;
  onUploadImage: (file: File) => void;
  onClose: () => void;
}

const DEFAULT_APPEARANCE: SlideAppearance = {
  theme: "auto",
  scrim: { enabled: true, strength: 0.35, position: "bottom", mode: "gradient" },
};

export default function SlideEditor({ format, data, onSave, onUploadImage, onClose }: SlideEditorProps) {
  const isCarousel = format === "carousel";
  const fileRef = useRef<HTMLInputElement>(null);

  const [headline, setHeadline] = useState(data.headline || "");
  const [subhead, setSubhead] = useState(data.subhead || data.support || "");
  const [body, setBody] = useState(data.body || "");
  const [bullets, setBullets] = useState((data.bullets || []).join("\\n"));
  const [cta, setCta] = useState(data.cta || "");

  // Appearance state
  const initial = data.appearance || DEFAULT_APPEARANCE;
  const [theme, setTheme] = useState<"auto" | "light" | "dark">(initial.theme);
  const [scrimEnabled, setScrimEnabled] = useState(initial.scrim.enabled);
  const [scrimStrength, setScrimStrength] = useState(String(initial.scrim.strength));
  const [scrimPosition, setScrimPosition] = useState(initial.scrim.position);
  const [scrimMode, setScrimMode] = useState(initial.scrim.mode);

  function handleSave() {
    const payload: Record<string, any> = {
      headline,
      subhead: subhead || null,
      support: subhead || null,
      appearance: {
        theme,
        scrim: {
          enabled: scrimEnabled,
          strength: parseFloat(scrimStrength),
          position: scrimPosition,
          mode: scrimMode,
        },
      },
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

      {/* ── Aparência ── */}
      <Separator />
      <div className="space-y-3">
        <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Aparência</h4>

        {/* Tema */}
        <div className="space-y-1.5">
          <Label className="text-xs">Tema</Label>
          <ToggleGroup type="single" value={theme} onValueChange={(v) => v && setTheme(v as any)} size="sm" className="justify-start">
            <ToggleGroupItem value="auto" className="gap-1.5 text-xs">
              <Monitor className="w-3.5 h-3.5" /> Auto
            </ToggleGroupItem>
            <ToggleGroupItem value="light" className="gap-1.5 text-xs">
              <Sun className="w-3.5 h-3.5" /> Claro
            </ToggleGroupItem>
            <ToggleGroupItem value="dark" className="gap-1.5 text-xs">
              <Moon className="w-3.5 h-3.5" /> Escuro
            </ToggleGroupItem>
          </ToggleGroup>
        </div>

        {/* Scrim */}
        <div className="flex items-center justify-between">
          <Label className="text-xs">Scrim (overlay)</Label>
          <Switch checked={scrimEnabled} onCheckedChange={setScrimEnabled} />
        </div>

        {scrimEnabled && (
          <div className="space-y-3 pl-1 border-l-2 border-muted ml-1">
            <div className="space-y-1.5 pl-3">
              <Label className="text-xs">Intensidade</Label>
              <ToggleGroup type="single" value={scrimStrength} onValueChange={(v) => v && setScrimStrength(v)} size="sm" className="justify-start">
                <ToggleGroupItem value="0.25" className="text-xs">Suave</ToggleGroupItem>
                <ToggleGroupItem value="0.35" className="text-xs">Médio</ToggleGroupItem>
                <ToggleGroupItem value="0.5" className="text-xs">Forte</ToggleGroupItem>
              </ToggleGroup>
            </div>

            <div className="space-y-1.5 pl-3">
              <Label className="text-xs">Posição</Label>
              <ToggleGroup type="single" value={scrimPosition} onValueChange={(v) => v && setScrimPosition(v as any)} size="sm" className="justify-start">
                <ToggleGroupItem value="top" className="text-xs">Topo</ToggleGroupItem>
                <ToggleGroupItem value="center" className="text-xs">Centro</ToggleGroupItem>
                <ToggleGroupItem value="bottom" className="text-xs">Base</ToggleGroupItem>
              </ToggleGroup>
            </div>

            <div className="space-y-1.5 pl-3">
              <Label className="text-xs">Modo</Label>
              <ToggleGroup type="single" value={scrimMode} onValueChange={(v) => v && setScrimMode(v as any)} size="sm" className="justify-start">
                <ToggleGroupItem value="gradient" className="text-xs">Gradiente</ToggleGroupItem>
                <ToggleGroupItem value="box" className="text-xs">Box</ToggleGroupItem>
              </ToggleGroup>
            </div>
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
