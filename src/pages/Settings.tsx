import { useEffect, useState } from "react";
import { fetchSettings, updateSettings } from "@/services/api";
import type { AppSettings } from "@/types/project";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Save } from "lucide-react";
import { toast } from "@/hooks/use-toast";

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings>({
    author_name: "",
    handle: "",
    brand_color: "#2a9d8f",
  });

  useEffect(() => {
    fetchSettings().then(setSettings);
  }, []);

  async function handleSave() {
    await updateSettings(settings);
    toast({ title: "Configurações salvas!" });
  }

  return (
    <div className="p-6 md:p-10 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-1">Configurações</h1>
      <p className="text-sm text-muted-foreground mb-8">
        Defina a assinatura padrão dos seus conteúdos
      </p>

      <div className="space-y-5">
        <div>
          <Label>Nome do autor / marca</Label>
          <Input
            value={settings.author_name}
            onChange={(e) => setSettings({ ...settings, author_name: e.target.value })}
            placeholder="Seu Nome"
          />
        </div>
        <div>
          <Label>Handle (@)</Label>
          <Input
            value={settings.handle}
            onChange={(e) => setSettings({ ...settings, handle: e.target.value })}
            placeholder="@seuhandle"
          />
        </div>
        <div>
          <Label>Cor da marca</Label>
          <div className="flex items-center gap-3">
            <input
              type="color"
              value={settings.brand_color}
              onChange={(e) => setSettings({ ...settings, brand_color: e.target.value })}
              className="w-10 h-10 rounded-md border cursor-pointer"
            />
            <Input
              value={settings.brand_color}
              onChange={(e) => setSettings({ ...settings, brand_color: e.target.value })}
              className="w-32"
            />
          </div>
        </div>

        <Button onClick={handleSave} className="gap-2">
          <Save className="w-4 h-4" /> Salvar configurações
        </Button>
      </div>

      <div className="mt-12 p-4 rounded-lg bg-muted text-sm text-muted-foreground">
        <p className="font-medium mb-1">🔌 Integração com Backend</p>
        <p>
          Este frontend está em modo mock (localStorage). Para o fluxo completo com
          geração via OpenAI e renderização PNG, conecte ao backend FastAPI.
        </p>
        <p className="mt-2 font-mono text-xs">
          API Base: <code>http://localhost:8000/api</code>
        </p>
      </div>
    </div>
  );
}
