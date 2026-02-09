import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Save, Loader2, Key, Image as ImageIcon, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { getSettings, updateSettings } from "@/lib/api";

export default function Settings() {
  const [settings, setSettings] = useState({
    api_key_source: "emergent",
    custom_api_key: "",
    image_source: "ai",
    language: "fr",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const data = await getSettings();
      setSettings({
        api_key_source: data.api_key_source || "emergent",
        custom_api_key: data.custom_api_key || "",
        image_source: data.image_source || "ai",
        language: data.language || "fr",
      });
    } catch (err) {
      // Default settings if none exist
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateSettings(settings);
      toast.success("Settings saved!");
    } catch (err) {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-8 lg:p-12 max-w-3xl mx-auto" data-testid="settings-page">
      <div className="mb-12 opacity-0 animate-fade-in-up" style={{ animationFillMode: "forwards" }}>
        <p className="text-xs font-mono tracking-widest uppercase text-indigo-400/60 mb-4">
          Configuration
        </p>
        <h1 className="text-5xl md:text-6xl font-light tracking-tight text-white leading-none mb-4" style={{ fontFamily: "'Fraunces', serif" }}>
          <span className="gradient-text">Settings</span>
        </h1>
      </div>

      <div className="space-y-8">
        {/* API Key Configuration */}
        <Card
          className="rounded-xl border border-white/5 bg-[#121212]/50 p-8 opacity-0 animate-fade-in-up animate-stagger-1"
          style={{ animationFillMode: "forwards" }}
          data-testid="api-key-settings-card"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center">
              <Key className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <h3 className="text-white font-medium" style={{ fontFamily: "'Fraunces', serif" }}>AI Provider</h3>
              <p className="text-white/40 text-sm">Gemini 2.5 Flash Lite</p>
            </div>
          </div>

          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-white/80">Use Emergent Universal Key</Label>
                <p className="text-xs text-white/30 mt-1">Free integrated key (credits-based)</p>
              </div>
              <Switch
                checked={settings.api_key_source === "emergent"}
                onCheckedChange={(checked) =>
                  setSettings({ ...settings, api_key_source: checked ? "emergent" : "custom" })
                }
                data-testid="emergent-key-switch"
              />
            </div>

            {settings.api_key_source === "custom" && (
              <div className="opacity-0 animate-fade-in-up" style={{ animationFillMode: "forwards" }}>
                <Label className="text-white/80 mb-2 block">Google API Key</Label>
                <Input
                  type="password"
                  value={settings.custom_api_key}
                  onChange={(e) => setSettings({ ...settings, custom_api_key: e.target.value })}
                  placeholder="AIza..."
                  className="bg-black/20 border-white/10 h-12"
                  data-testid="custom-api-key-input"
                />
                <p className="text-xs text-white/20 mt-2">
                  Get your key at: console.cloud.google.com
                </p>
              </div>
            )}
          </div>
        </Card>

        {/* Image Source */}
        <Card
          className="rounded-xl border border-white/5 bg-[#121212]/50 p-8 opacity-0 animate-fade-in-up animate-stagger-2"
          style={{ animationFillMode: "forwards" }}
          data-testid="image-settings-card"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
              <ImageIcon className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h3 className="text-white font-medium" style={{ fontFamily: "'Fraunces', serif" }}>Image Source</h3>
              <p className="text-white/40 text-sm">How to generate book illustrations</p>
            </div>
          </div>

          <Select
            value={settings.image_source}
            onValueChange={(val) => setSettings({ ...settings, image_source: val })}
          >
            <SelectTrigger className="bg-black/20 border-white/10 h-12" data-testid="image-source-settings-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ai">AI Generation (Gemini Nano Banana)</SelectItem>
              <SelectItem value="stock">Stock Photos (Unsplash)</SelectItem>
              <SelectItem value="both">Both (AI first, stock fallback)</SelectItem>
            </SelectContent>
          </Select>
        </Card>

        {/* Language */}
        <Card
          className="rounded-xl border border-white/5 bg-[#121212]/50 p-8 opacity-0 animate-fade-in-up animate-stagger-3"
          style={{ animationFillMode: "forwards" }}
          data-testid="language-settings-card"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
              <Globe className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-white font-medium" style={{ fontFamily: "'Fraunces', serif" }}>Default Language</h3>
              <p className="text-white/40 text-sm">Language for generated books</p>
            </div>
          </div>

          <Select
            value={settings.language}
            onValueChange={(val) => setSettings({ ...settings, language: val })}
          >
            <SelectTrigger className="bg-black/20 border-white/10 h-12" data-testid="default-language-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="fr">Francais</SelectItem>
              <SelectItem value="en">English</SelectItem>
            </SelectContent>
          </Select>
        </Card>

        {/* Save Button */}
        <Button
          onClick={handleSave}
          disabled={saving}
          data-testid="save-settings-btn"
          className="bg-indigo-500 hover:bg-indigo-600 text-white h-12 px-8 glow-button w-full"
        >
          {saving ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Save className="w-4 h-4 mr-2" />
          )}
          Save Settings
        </Button>
      </div>
    </div>
  );
}
