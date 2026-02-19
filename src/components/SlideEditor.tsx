import { useState, useRef, useEffect } from "react";
import type { UiSlide, SlideAppearance, TemplateVariantInfo } from "@/types/project";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Upload, Save, X, Sun, Moon, Monitor, LayoutTemplate } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface SlideEditorProps {
  format: "carousel" | "stories_10x";
  data: UiSlide;
  familyName?: string;
  onSave: (payload: Record<string, any>) => void;
  onUploadImage: (file: File) => void;
  onClose: () => void;
}

// Slot character limits from slots.json (premium_editorial_v1)
const SLOT_LIMITS: Record<string, { max_chars?: number; max_items?: number; max_chars_per_item?: number }> = {
  title: { max_chars: 68 },
  headline: { max_chars: 68 },
  subtitle: { max_chars: 90 },
  subhead: { max_chars: 90 },
  body: { max_chars: 220 },
  bullets: { max_items: 5, max_chars_per_item: 48 },
  cta_title: { max_chars: 50 },
  cta_body: { max_chars: 180 },
  cta_button: { max_chars: 20 },
  cta: { max_chars: 20 },
  brand: { max_chars: 32 },
  kicker: { max_chars: 32 },
  category: { max_chars: 32 },
};

function CharCount({ value, max }: { value: string; max: number }) {
  const len = value.length;
  const over = len > max;
  return (
    <span className={`text-[10px] tabular-nums ${over ? "text-destructive font-semibold" : "text-muted-foreground"}`}>
      {len}/{max}
    </span>
  );
}

const DEFAULT_APPEARANCE: SlideAppearance = {
  theme: "auto",
  scrim: { enabled: true, strength: 0.35, position: "bottom", mode: "gradient" },
};

// Role to registry key mapping
const ROLE_REGISTRY_KEY: Record<string, string> = {
  cover: "cover",
  body: "body",
  cta: "cta",
  frame: "frame",
  frame_cta: "cta",
};

export default function SlideEditor({ format, data, familyName, onSave, onUploadImage, onClose }: SlideEditorProps) {
  const isCarousel = format === "carousel";
  const fileRef = useRef<HTMLInputElement>(null);

  const [headline, setHeadline] = useState(data.headline || "");
  const [subhead, setSubhead] = useState(data.subhead || data.support || "");
  const [body, setBody] = useState(data.body || "");
  const [bullets, setBullets] = useState((data.bullets || []).join("\n"));
  const [cta, setCta] = useState(data.cta || "");
  const [templateVariant, setTemplateVariant] = useState(data.template_variant || "");
  const [availableVariants, setAvailableVariants] = useState<TemplateVariantInfo[]>([]);

  // Appearance state
  const initial = data.appearance || DEFAULT_APPEARANCE;
  const [theme, setTheme] = useState<"auto" | "light" | "dark">(initial.theme);
  const [scrimEnabled, setScrimEnabled] = useState(initial.scrim.enabled);
  const [scrimStrength, setScrimStrength] = useState(String(initial.scrim.strength));
  const [scrimPosition, setScrimPosition] = useState(initial.scrim.position);
  const [scrimMode, setScrimMode] = useState(initial.scrim.mode);

  // Load available variants from registry.json
  useEffect(() => {
    fetch("/templates/registry.json")
      .then((r) => r.json())
      .then((registry) => {
        const formatKey = isCarousel ? "carousel" : "stories";
        const roleKey = ROLE_REGISTRY_KEY[data.role] || data.role;

        // Try family first, then classic
        const family = familyName && familyName !== "classic" ? familyName : null;
        let variants: any[] = [];

        if (family && registry[family]?.[formatKey]?.[roleKey]) {
          variants = registry[family][formatKey][roleKey];
        } else if (registry[formatKey]?.[roleKey]) {
          variants = registry[formatKey][roleKey];
        }

        setAvailableVariants(
          variants.map((v: any) => ({
            id: v.id,
            label: v.label,
            theme: v.theme,
          }))
        );
      })
      .catch(() => {});
  }, [data.role, format, familyName, isCarousel]);

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

    if (templateVariant) {
      payload.template_variant = templateVariant;
    }

    if (isCarousel) {
      payload.body = body || null;
      payload.bullets = bullets ? bullets.split("\n").filter(Boolean) : [];
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

      {/* ── Template Variant Selector ── */}
      {availableVariants.length > 1 && (
        <div className="space-y-1.5">
          <Label className="text-xs flex items-center gap-1.5">
            <LayoutTemplate className="w-3.5 h-3.5" /> Template do card
          </Label>
          <Select value={templateVariant || "__default__"} onValueChange={(v) => setTemplateVariant(v === "__default__" ? "" : v)}>
            <SelectTrigger className="h-9">
              <SelectValue placeholder="Padrão do projeto" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__default__">Padrão do projeto</SelectItem>
              {availableVariants.map((v) => (
                <SelectItem key={v.id} value={v.id}>
                  {v.label} {v.theme === "dark" ? "🌙" : "☀️"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      <div className="grid gap-3">
        <div>
          <div className="flex items-center justify-between mb-1">
            <Label className="text-xs">Headline</Label>
            <CharCount value={headline} max={SLOT_LIMITS.title.max_chars!} />
          </div>
          <Input
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            className={headline.length > SLOT_LIMITS.title.max_chars! ? "border-destructive" : ""}
          />
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <Label className="text-xs">{isCarousel ? "Subtítulo" : "Texto de suporte"}</Label>
            <CharCount value={subhead} max={SLOT_LIMITS.subtitle.max_chars!} />
          </div>
          <Input
            value={subhead}
            onChange={(e) => setSubhead(e.target.value)}
            className={subhead.length > SLOT_LIMITS.subtitle.max_chars! ? "border-destructive" : ""}
          />
        </div>

        {isCarousel && data.role === "body" && (
          <>
            <div>
              <div className="flex items-center justify-between mb-1">
                <Label className="text-xs">Corpo do texto</Label>
                <CharCount value={body} max={SLOT_LIMITS.body.max_chars!} />
              </div>
              <Textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                rows={3}
                className={body.length > SLOT_LIMITS.body.max_chars! ? "border-destructive" : ""}
              />
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <Label className="text-xs">Bullets (um por linha)</Label>
                <span className="text-[10px] text-muted-foreground">
                  {bullets.split("\n").filter(Boolean).length}/{SLOT_LIMITS.bullets.max_items} itens
                </span>
              </div>
              <Textarea
                value={bullets}
                onChange={(e) => setBullets(e.target.value)}
                rows={3}
                placeholder={`Ponto 1\nPonto 2\nPonto 3`}
              />
              {bullets.split("\n").filter(Boolean).some((b) => b.length > SLOT_LIMITS.bullets.max_chars_per_item!) && (
                <p className="text-[10px] text-destructive mt-1">
                  ⚠ Algum item excede {SLOT_LIMITS.bullets.max_chars_per_item} caracteres
                </p>
              )}
            </div>
          </>
        )}

        {(data.role === "cta" || data.role === "frame_cta") && (
          <div>
            <div className="flex items-center justify-between mb-1">
              <Label className="text-xs">CTA</Label>
              <CharCount value={cta} max={SLOT_LIMITS.cta.max_chars!} />
            </div>
            <Input
              value={cta}
              onChange={(e) => setCta(e.target.value)}
              className={cta.length > SLOT_LIMITS.cta.max_chars! ? "border-destructive" : ""}
            />
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
