import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Compass, TrendingUp, BookOpen, ArrowRight, Loader2, Sparkles, ChefHat, Wrench, Heart, Baby, Lightbulb } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { discoverThemes } from "@/lib/api";

const categories = [
  { value: "all", label: "All Categories", icon: Compass },
  { value: "guide", label: "Guides", icon: Lightbulb },
  { value: "recipe", label: "Recipes", icon: ChefHat },
  { value: "diy", label: "DIY / Crafts", icon: Wrench },
  { value: "self-help", label: "Self-Help", icon: Heart },
  { value: "children", label: "Children", icon: Baby },
];

const demandColors = {
  high: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  medium: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  low: "bg-red-500/20 text-red-400 border-red-500/30",
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [themes, setThemes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [language, setLanguage] = useState("fr");
  const [category, setCategory] = useState("all");

  const handleDiscover = async () => {
    setLoading(true);
    try {
      const data = await discoverThemes({
        category: category === "all" ? null : category,
        language,
      });
      if (data.themes && data.themes.length > 0) {
        setThemes(data.themes);
        toast.success(language === "fr" ? "Thématiques découvertes !" : "Themes discovered!");
      } else {
        toast.error(data.error || "No themes found");
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to discover themes");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectTheme = (theme) => {
    navigate("/create", { state: { theme: theme.title, language } });
  };

  return (
    <div className="p-8 lg:p-12 max-w-7xl mx-auto" data-testid="dashboard-page">
      {/* Hero */}
      <div className="mb-16 opacity-0 animate-fade-in-up" style={{ animationFillMode: "forwards" }}>
        <p className="text-xs font-mono tracking-widest uppercase text-indigo-400/60 mb-4">
          Theme Discovery
        </p>
        <h1 className="text-5xl md:text-6xl font-light tracking-tight text-white leading-none mb-6" style={{ fontFamily: "'Fraunces', serif" }}>
          Discover Trending<br />
          <span className="gradient-text">Book Themes</span>
        </h1>
        <p className="text-lg text-white/50 max-w-xl leading-relaxed">
          {language === "fr"
            ? "Explorez les thématiques les plus recherchées sur Amazon et créez votre prochain best-seller."
            : "Explore the most searched themes on Amazon and create your next bestseller."}
        </p>
      </div>

      {/* Controls */}
      <div
        className="flex flex-wrap items-center gap-4 mb-12 opacity-0 animate-fade-in-up animate-stagger-1"
        style={{ animationFillMode: "forwards" }}
        data-testid="theme-controls"
      >
        <Select value={language} onValueChange={setLanguage}>
          <SelectTrigger className="w-40 bg-black/20 border-white/10 h-12" data-testid="language-select">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="fr">Francais</SelectItem>
            <SelectItem value="en">English</SelectItem>
          </SelectContent>
        </Select>

        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="w-48 bg-black/20 border-white/10 h-12" data-testid="category-select">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {categories.map((cat) => (
              <SelectItem key={cat.value} value={cat.value}>
                {cat.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          onClick={handleDiscover}
          disabled={loading}
          data-testid="discover-themes-btn"
          className="bg-indigo-500 hover:bg-indigo-600 text-white h-12 px-8 rounded-lg glow-button transition-all duration-300"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              {language === "fr" ? "Analyse en cours..." : "Analyzing..."}
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4 mr-2" />
              {language === "fr" ? "Decouvrir les themes" : "Discover Themes"}
            </>
          )}
        </Button>
      </div>

      {/* Themes Grid */}
      {themes.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="themes-grid">
          {themes.map((theme, i) => (
            <Card
              key={i}
              data-testid={`theme-card-${i}`}
              className={`group rounded-xl border border-white/5 bg-[#121212]/50 backdrop-blur-sm hover:border-indigo-500/30 transition-all duration-500 cursor-pointer overflow-hidden relative p-6 opacity-0 animate-fade-in-up`}
              style={{ animationFillMode: "forwards", animationDelay: `${i * 0.1}s` }}
              onClick={() => handleSelectTheme(theme)}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-indigo-400" />
                  <Badge
                    variant="outline"
                    className={`text-[10px] font-mono ${demandColors[theme.demand_level] || demandColors.medium}`}
                  >
                    {theme.demand_level} demand
                  </Badge>
                </div>
                <Badge variant="outline" className="text-[10px] font-mono text-white/40 border-white/10">
                  {theme.competition} comp.
                </Badge>
              </div>

              <h3 className="text-white text-lg font-medium mb-2 group-hover:text-indigo-300 transition-colors" style={{ fontFamily: "'Fraunces', serif" }}>
                {theme.title}
              </h3>
              <p className="text-white/40 text-sm leading-relaxed mb-4">
                {theme.description}
              </p>

              {theme.categories && (
                <div className="flex flex-wrap gap-2 mb-4">
                  {theme.categories.map((cat, j) => (
                    <span
                      key={j}
                      className="text-[10px] font-mono px-2 py-1 rounded bg-white/5 text-white/50"
                    >
                      {cat}
                    </span>
                  ))}
                </div>
              )}

              <div className="flex items-center text-indigo-400 text-sm opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                <span>{language === "fr" ? "Explorer cette thematique" : "Explore this theme"}</span>
                <ArrowRight className="w-4 h-4 ml-2" />
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Empty State */}
      {themes.length === 0 && !loading && (
        <div
          className="text-center py-24 opacity-0 animate-fade-in-up animate-stagger-2"
          style={{ animationFillMode: "forwards" }}
          data-testid="empty-state"
        >
          <div className="w-20 h-20 rounded-2xl bg-indigo-500/10 flex items-center justify-center mx-auto mb-6">
            <Compass className="w-8 h-8 text-indigo-400/60" />
          </div>
          <h3 className="text-xl text-white/60 mb-2" style={{ fontFamily: "'Fraunces', serif" }}>
            {language === "fr" ? "Pret a explorer ?" : "Ready to explore?"}
          </h3>
          <p className="text-white/30 text-sm max-w-md mx-auto">
            {language === "fr"
              ? "Cliquez sur 'Decouvrir les themes' pour analyser les tendances Amazon KDP actuelles."
              : "Click 'Discover Themes' to analyze current Amazon KDP trends."}
          </p>
        </div>
      )}
    </div>
  );
}
