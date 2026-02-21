import { useState, useRef, useEffect, useMemo } from "react";
import type { UiSlide, SlideAppearance, TemplateVariantInfo } from "@/types/project";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Upload, Save, X, Sun, Moon, Monitor, LayoutTemplate, AlertTriangle } from "lucide-react";
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

interface SlotSpec {
  required?: boolean;
  max_chars?: number;
  max_lines?: number;
  max_items?: number;
  max_chars_per_item?: number;
  description?: string;
}

const FALLBACK_LIMITS: Record<string, SlotSpec> = {
  headline: { max_chars: 68 },
  title: { max_chars: 68 },
  subtitle: { max_chars: 90 },
  subhead: { max_chars: 90 },
  body: { max_chars: 220 },
  bullets: { max_items: 5, max_chars_per_item: 48 },
  cta: { max_chars: 20 },
  cta_title: { max_chars: 50 },
  cta_body: { max_chars: 180 },
  cta_button: { max_chars: 20 },
  support: { max_chars: 80 },
  kicker: { max_chars: 32 },
  brand: { max_chars: 32 },
};

function CharCount({ value, max }: { value: string; max: number }) {
  const len = value.length;
  const ratio = len / max;
  const colorClass = ratio > 1
    ? "text-destructive font-semibold"
    : ratio > 0.8
    ? "text-amber-500 font-medium"
    : "text-muted-foreground";
  return (
    <span className={`text-[10px] tabular-nums ${colorClass}`}>
      {len}/{max}
    </span>
  );
}

const DEFAULT_APPEARANCE: SlideAppearance = {
  theme: "auto",
  scrim: { enabled: true, strength: 0.35, position: "bottom", mode: "gradient" },
};

const ROLE_REGISTRY_KEY: Record<string, string> = {
  cover: "cover",
  body: "body",
  cta: "cta",
  frame: "frame",
  frame_cta: "cta",
};

const ROLE_SLOTS_PATH: Record<string, Record<string, string>> = {
  carousel: {
    cover: "layouts/carousel/cover/slots.json",
    body: "layouts/carousel/body/slots.json",
    cta: "layouts/carousel/cta/slots.json",
  },
  stories: {
    frame: "layouts/stories/frame/slots.json",
    cta: "layouts/stories/cta/slots.json",
  },
};

export default function SlideEditor({ format, data, familyName, onSave, onUploadImage, onClose }: SlideEditorProps) {
  const isCarousel = format === "carousel";
  const formatKey = isCarousel ? "carousel" : "stories";
  const roleKey = ROLE_REGISTRY_KEY[data.role] || data.role;
  const fileRef = useRef<HTMLInputElement>(null);

  const [slotSchema, setSlotSchema] = useState<Record<string, SlotSpec>>({});
  const [schemaLoaded, setSchemaLoaded] = useState(false);

  const payload = data.payload || {};

  const firstNonEmpty = (source: Record<string, any>, keys: string[]) => {
    for (const k of keys) {
      const value = source?.[k];
      if (Array.isArray(value) && value.length > 0) return value;
      if (typeof value === "string" && value.trim()) return value;
      if (value !== undefined && value !== null) return value;
    }
    return "";
  };

  const toBulletsText = (source: any) => {
    if (Array.isArray(source)) return source.join("\n");
    if (typeof source === "string") return source;
    return "";
  };

  const headlineKeys = ["headline", "title", "cta_title", "Title", "Headline", "heading", "h1"];
  const subheadKeys = ["subhead", "subtitle", "support", "kicker", "Subtitle", "Subhead", "description"];
  const bodyKeys = ["body", "text", "content", "Body", "paragraph"];
  const ctaKeys = ["cta", "cta_button", "cta_title", "button"];
  const bulletKeys = ["bullets", "Bullets", "list"];

  const [headline, setHeadline] = useState(String(firstNonEmpty(payload, headlineKeys) || ""));
  const [subhead, setSubhead] = useState(String(firstNonEmpty(payload, subheadKeys) || ""));
  const [body, setBody] = useState(String(firstNonEmpty(payload, bodyKeys) || ""));
  const [bullets, setBullets] = useState(toBulletsText(firstNonEmpty(payload, bulletKeys)));
  const [cta, setCta] = useState(String(firstNonEmpty(payload, ctaKeys) || ""));
  const [templateVariant, setTemplateVariant] = useState(payload.template_variant || data.template_variant || "");

  useEffect(() => {
    const currentPayload = data.payload || {};
    setHeadline(String(firstNonEmpty(currentPayload, headlineKeys) || ""));
    setSubhead(String(firstNonEmpty(currentPayload, subheadKeys) || ""));
    setBody(String(firstNonEmpty(currentPayload, bodyKeys) || ""));
    setBullets(toBulletsText(firstNonEmpty(currentPayload, bulletKeys)));
    setCta(String(firstNonEmpty(currentPayload, ctaKeys) || ""));
    setTemplateVariant(currentPayload.template_variant || data.template_variant || "");
  }, [data]);

  const [availableVariants, setAvailableVariants] = useState<TemplateVariantInfo[]>([]);

  const initial = data.appearance || DEFAULT_APPEARANCE;
  const [theme, setTheme] = useState<"auto" | "light" | "dark">(initial.theme);
  const [scrimEnabled, setScrimEnabled] = useState(initial.scrim.enabled);
  const [scrimStrength, setScrimStrength] = useState(String(initial.scrim.strength));
  const [scrimPosition, setScrimPosition] = useState(initial.scrim.position);
  const [scrimMode, setScrimMode] = useState(initial.scrim.mode);

  useEffect(() => {
    const family = familyName && familyName !== "classic" ? familyName : null;

    if (family) {
      fetch(`/templates/families/${family}/slots.json`)
        .then((r) => r.json())
        .then((schema) => {
          setSlotSchema(schema.slots || {});
          setSchemaLoaded(true);
        })
        .catch(() => {
          setSlotSchema(FALLBACK_LIMITS);
          setSchemaLoaded(true);
        });
    } else {
      const slotsPath = ROLE_SLOTS_PATH[formatKey]?.[roleKey];
      if (slotsPath) {
        fetch(`/templates/${slotsPath}`)
          .then((r) => r.json())
          .then((schema) => {
            setSlotSchema(schema.slots || {});
            setSchemaLoaded(true);
          })
          .catch(() => {
            setSlotSchema(FALLBACK_LIMITS);
            setSchemaLoaded(true);
          });
      } else {
        setSlotSchema(FALLBACK_LIMITS);
        setSchemaLoaded(true);
      }
    }
  }, [familyName, formatKey, roleKey]);

  useEffect(() => {
    fetch("/templates/registry.json")
      .then((r) => r.json())
      .then((registry) => {
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
            theme: v.theme || "light",
          }))
        );
      })
      .catch(() => {});
  }, [data.role, formatKey, familyName, roleKey]);

  const getLimit = (slot: string) => slotSchema[slot] || FALLBACK_LIMITS[slot] || {};

  const supportsBullets = !!slotSchema.bullets;
  const supportsBody = !!slotSchema.body;
  const supportsCta = !!(slotSchema.cta || slotSchema.cta_button);
  const supportsSubhead = !!(slotSchema.subhead || slotSchema.subtitle || slotSchema.support);

  const headlineKey = slotSchema.headline ? "headline" : slotSchema.title ? "title" : "headline";
  const headlineLimit = getLimit(headlineKey);

  const subheadKey = slotSchema.subhead ? "subhead" : slotSchema.subtitle ? "subtitle" : slotSchema.support ? "support" : "subhead";
  const subheadLimit = getLimit(subheadKey);

  const ctaKey = slotSchema.cta ? "cta" : slotSchema.cta_button ? "cta_button" : "cta";
  const ctaLimit = getLimit(ctaKey);

  const warnings = useMemo(() => {
    const w: string[] = [];
    if (headlineLimit.max_chars && headline.length > headlineLimit.max_chars) {
      w.push(`Headline excede ${headlineLimit.max_chars} caracteres`);
    }
    if (subheadLimit.max_chars && subhead.length > subheadLimit.max_chars) {
      w.push(`Subtítulo excede ${subheadLimit.max_chars} caracteres`);
    }
    const bodyLimit = getLimit("body");
    if (supportsBody && bodyLimit.max_chars && body.length > bodyLimit.max_chars) {
      w.push(`Corpo excede ${bodyLimit.max_chars} caracteres`);
    }
    const bulletsLimit = getLimit("bullets");
    if (supportsBullets && bulletsLimit.max_items) {
      const items = bullets.split("\n").filter(Boolean);
      if (items.length > bulletsLimit.max_items) {
        w.push(`Bullets excedem ${bulletsLimit.max_items} itens`);
      }
      if (bulletsLimit.max_chars_per_item && items.some((b) => b.length > bulletsLimit.max_chars_per_item!)) {
        w.push(`Algum bullet excede ${bulletsLimit.max_chars_per_item} caracteres`);
      }
    }
    if (supportsCta && ctaLimit.max_chars && cta.length > ctaLimit.max_chars) {
      w.push(`CTA excede ${ctaLimit.max_chars} caracteres`);
    }
    return w;
  }, [headline, subhead, body, bullets, cta, headlineLimit, subheadLimit, ctaLimit, supportsBody, supportsBullets, supportsCta]);

  // --- SALVAMENTO NÃO-DESTRUTIVO ---
  function handleSave() {
    const updatedPayload: Record<string, any> = { ...(data.payload || {}) };

    updatedPayload.headline = headline || null;
    updatedPayload.title = headline || null;

    if (supportsSubhead) {
      updatedPayload.subhead = subhead || null;
      updatedPayload.subtitle = subhead || null;
      updatedPayload.support = subhead || null;
    }

    if (supportsCta && (data.role === "cta" || data.role === "frame_cta")) {
      updatedPayload.cta = cta || null;
      updatedPayload.cta_button = cta || null;
      updatedPayload.cta_title = headline || null;
    }

    if (supportsBody && (data.role === "body" || data.role === "frame")) {
      updatedPayload.body = body || null;
    }

    if (supportsBullets && (data.role === "body" || data.role === "frame")) {
      updatedPayload.bullets = bullets ? bullets.split("\n").map((item) => item.trim()).filter(Boolean) : [];
    }

    updatedPayload.appearance = {
      theme,
      scrim: {
        enabled: scrimEnabled,
        strength: parseFloat(scrimStrength),
        position: scrimPosition,
        mode: scrimMode,
      },
    };

    if (templateVariant) {
      updatedPayload.template_variant = templateVariant;
    } else {
      delete updatedPayload.template_variant;
    }

    if (warnings.length > 0) {
      toast.warning(`Salvo com avisos: ${warnings.length} campo(s) excedem o limite`);
    } else {
      toast.success("Card salvo! Renderize novamente para ver o resultado final.");
    }

    onSave(updatedPayload);
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
            {headlineLimit.max_chars && <CharCount value={headline} max={headlineLimit.max_chars} />}
          </div>
          <Input
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            className={headlineLimit.max_chars && headline.length > headlineLimit.max_chars ? "border-destructive" : ""}
          />
        </div>

        {supportsSubhead && (
          <div>
            <div className="flex items-center justify-between mb-1">
              <Label className="text-xs">
                {subheadKey === "support" ? "Texto de suporte" : "Subtítulo"}
              </Label>
              {subheadLimit.max_chars && <CharCount value={subhead} max={subheadLimit.max_chars} />}
            </div>
            <Input
              value={subhead}
              onChange={(e) => setSubhead(e.target.value)}
              className={subheadLimit.max_chars && subhead.length > subheadLimit.max_chars ? "border-destructive" : ""}
            />
          </div>
        )}

        {supportsBody && (data.role === "body" || data.role === "frame") && (
          <div>
            <div className="flex items-center justify-between mb-1">
              <Label className="text-xs">Corpo do texto</Label>
              {getLimit("body").max_chars && <CharCount value={body} max={getLimit("body").max_chars!} />}
            </div>
            <Textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={3}
              className={getLimit("body").max_chars && body.length > getLimit("body").max_chars! ? "border-destructive" : ""}
            />
          </div>
        )}

        {supportsBullets && (data.role === "body" || data.role === "frame") && (
          <div>
            <div className="flex items-center justify-between mb-1">
              <Label className="text-xs">Bullets (um por linha)</Label>
              <span className="text-[10px] text-muted-foreground">
                {bullets.split("\n").filter(Boolean).length}/{getLimit("bullets").max_items || 5} itens
              </span>
            </div>
            <Textarea
              value={bullets}
              onChange={(e) => setBullets(e.target.value)}
              rows={3}
              placeholder={`Ponto 1\nPonto 2\nPonto 3`}
            />
            {getLimit("bullets").max_chars_per_item &&
              bullets.split("\n").filter(Boolean).some((b) => b.length > getLimit("bullets").max_chars_per_item!) && (
                <p className="text-[10px] text-destructive mt-1">
                  ⚠ Algum item excede {getLimit("bullets").max_chars_per_item} caracteres
                </p>
              )}
          </div>
        )}

        {(data.role === "cta" || data.role === "frame_cta") && supportsCta && (
          <div>
            <div className="flex items-center justify-between mb-1">
              <Label className="text-xs">CTA</Label>
              {ctaLimit.max_chars && <CharCount value={cta} max={ctaLimit.max_chars} />}
            </div>
            <Input
              value={cta}
              onChange={(e) => setCta(e.target.value)}
              className={ctaLimit.max_chars && cta.length > ctaLimit.max_chars ? "border-destructive" : ""}
            />
          </div>
        )}
      </div>

      <Separator />
      <div className="space-y-3">
        <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Aparência</h4>

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

      {warnings.length > 0 && (
        <>
          <Separator />
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 space-y-1">
            <div className="flex items-center gap-1.5 text-amber-600 text-xs font-semibold">
              <AlertTriangle className="w-3.5 h-3.5" /> Avisos
            </div>
            {warnings.map((w, i) => (
              <p key={i} className="text-[11px] text-amber-600">{w}</p>
            ))}
          </div>
        </>
      )}

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
            if (file) {
              if (file.size > 10 * 1024 * 1024) {
                toast.error("Imagem excede 10MB. Escolha uma imagem menor.");
                return;
              }
              onUploadImage(file);
            }
          }}
        />
      </div>
    </div>
  );
}
