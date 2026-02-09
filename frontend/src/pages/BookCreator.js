import { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Lightbulb, Loader2, Check, ArrowRight, ArrowLeft, BookOpen, Sparkles,
  FileText, PenTool, Image as ImageIcon
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  generateIdeas, createBook, generateOutline, updateOutline,
  generateChapter, generateAllChapters, getBookProgress
} from "@/lib/api";

const steps = [
  { id: "ideas", label: "Choose Idea", icon: Lightbulb },
  { id: "customize", label: "Customize", icon: PenTool },
  { id: "outline", label: "Outline", icon: FileText },
  { id: "writing", label: "Writing", icon: BookOpen },
];

export default function BookCreator() {
  const location = useLocation();
  const navigate = useNavigate();
  const themeFromDashboard = location.state?.theme || "";
  const langFromDashboard = location.state?.language || "fr";

  const [step, setStep] = useState(0);
  const [theme, setTheme] = useState(themeFromDashboard);
  const [language, setLanguage] = useState(langFromDashboard);
  const [ideas, setIdeas] = useState([]);
  const [selectedIdea, setSelectedIdea] = useState(null);
  const [loading, setLoading] = useState(false);
  const [bookId, setBookId] = useState(null);
  const [outline, setOutline] = useState([]);
  const [writingProgress, setWritingProgress] = useState(null);
  const [imageSource, setImageSource] = useState("ai");

  // Auto-discover ideas if theme is provided
  useEffect(() => {
    if (themeFromDashboard && ideas.length === 0) {
      handleGenerateIdeas();
    }
    // eslint-disable-next-line
  }, []);

  const handleGenerateIdeas = async () => {
    if (!theme.trim()) {
      toast.error(language === "fr" ? "Entrez une thematique" : "Enter a theme");
      return;
    }
    setLoading(true);
    try {
      const data = await generateIdeas({ theme, language });
      if (data.ideas?.length > 0) {
        setIdeas(data.ideas);
        toast.success(language === "fr" ? "Idees generees !" : "Ideas generated!");
      } else {
        toast.error(data.error || "No ideas generated");
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to generate ideas");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectIdea = (idea) => {
    setSelectedIdea(idea);
    setStep(1);
  };

  const handleCreateBook = async () => {
    if (!selectedIdea) return;
    setLoading(true);
    try {
      const book = await createBook({
        title: selectedIdea.title,
        subtitle: selectedIdea.subtitle,
        description: selectedIdea.description,
        category: selectedIdea.category,
        language,
        target_pages: selectedIdea.estimated_pages || 100,
        image_source: imageSource,
      });
      setBookId(book.id);
      toast.success(language === "fr" ? "Livre cree ! Generation du plan..." : "Book created! Generating outline...");
      
      // Generate outline
      const outlineData = await generateOutline(book.id);
      if (outlineData.outline) {
        setOutline(outlineData.outline);
        setStep(2);
        toast.success(language === "fr" ? "Plan genere !" : "Outline generated!");
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create book");
    } finally {
      setLoading(false);
    }
  };

  const handleApproveOutline = async () => {
    if (!bookId) return;
    setLoading(true);
    try {
      await updateOutline(bookId, outline);
      setStep(3);
      toast.success(language === "fr" ? "Plan approuve ! Lancement de l'ecriture..." : "Outline approved! Starting writing...");
      
      // Start generating all chapters
      await generateAllChapters(bookId);
      pollProgress();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to approve outline");
    } finally {
      setLoading(false);
    }
  };

  const pollProgress = () => {
    const interval = setInterval(async () => {
      try {
        const progress = await getBookProgress(bookId);
        setWritingProgress(progress);
        
        if (progress.status === "chapters_complete") {
          clearInterval(interval);
          toast.success(language === "fr" ? "Livre termine ! Rendez-vous dans la bibliotheque." : "Book complete! Check the library.");
          navigate(`/book/${bookId}`);
        } else if (progress.status === "error") {
          clearInterval(interval);
          toast.error(progress.error || "Error during generation");
        }
      } catch (err) {
        // Keep polling
      }
    }, 5000);
  };

  return (
    <div className="p-8 lg:p-12 max-w-5xl mx-auto" data-testid="book-creator-page">
      {/* Steps */}
      <div className="flex items-center gap-2 mb-12" data-testid="creation-steps">
        {steps.map((s, i) => (
          <div key={s.id} className="flex items-center">
            <div
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all duration-300 ${
                i === step
                  ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                  : i < step
                  ? "bg-emerald-500/10 text-emerald-400"
                  : "text-white/30"
              }`}
            >
              {i < step ? (
                <Check className="w-4 h-4" />
              ) : (
                <s.icon className="w-4 h-4" />
              )}
              <span className="hidden sm:inline">{s.label}</span>
            </div>
            {i < steps.length - 1 && (
              <ArrowRight className="w-4 h-4 text-white/10 mx-1" />
            )}
          </div>
        ))}
      </div>

      {/* Step 0: Ideas */}
      {step === 0 && (
        <div className="opacity-0 animate-fade-in-up" style={{ animationFillMode: "forwards" }}>
          <p className="text-xs font-mono tracking-widest uppercase text-indigo-400/60 mb-4">
            Step 1 / 4
          </p>
          <h2 className="text-3xl md:text-4xl font-light tracking-tight text-white mb-8" style={{ fontFamily: "'Fraunces', serif" }}>
            {language === "fr" ? "Choisissez votre idee" : "Choose your idea"}
          </h2>

          {/* Theme Input */}
          <div className="flex gap-4 mb-10" data-testid="theme-input-section">
            <Input
              value={theme}
              onChange={(e) => setTheme(e.target.value)}
              placeholder={language === "fr" ? "Entrez une thematique (ex: cuisine vegane, meditation...)" : "Enter a theme (e.g.: vegan cooking, meditation...)"}
              className="flex-1 bg-black/20 border-white/10 h-12 text-base"
              data-testid="theme-input"
            />
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger className="w-32 bg-black/20 border-white/10 h-12" data-testid="creator-language-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="fr">Francais</SelectItem>
                <SelectItem value="en">English</SelectItem>
              </SelectContent>
            </Select>
            <Button
              onClick={handleGenerateIdeas}
              disabled={loading}
              data-testid="generate-ideas-btn"
              className="bg-indigo-500 hover:bg-indigo-600 text-white h-12 px-6 glow-button"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            </Button>
          </div>

          {/* Ideas Grid */}
          {ideas.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6" data-testid="ideas-grid">
              {ideas.map((idea, i) => (
                <Card
                  key={i}
                  data-testid={`idea-card-${i}`}
                  onClick={() => handleSelectIdea(idea)}
                  className="group rounded-xl border border-white/5 bg-[#121212]/50 hover:border-indigo-500/30 transition-all duration-500 cursor-pointer p-6"
                >
                  <div className="flex items-center gap-2 mb-3">
                    <Badge variant="outline" className="text-[10px] font-mono text-indigo-400 border-indigo-500/30">
                      {idea.category}
                    </Badge>
                    <Badge variant="outline" className="text-[10px] font-mono text-white/40 border-white/10">
                      ~{idea.estimated_pages}p
                    </Badge>
                  </div>
                  <h3 className="text-white text-lg font-medium mb-1 group-hover:text-indigo-300 transition-colors" style={{ fontFamily: "'Fraunces', serif" }}>
                    {idea.title}
                  </h3>
                  {idea.subtitle && (
                    <p className="text-white/50 text-sm mb-3">{idea.subtitle}</p>
                  )}
                  <p className="text-white/35 text-sm leading-relaxed mb-3">{idea.description}</p>
                  <p className="text-[11px] text-indigo-400/60">
                    <span className="font-medium">Audience:</span> {idea.target_audience}
                  </p>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Step 1: Customize */}
      {step === 1 && selectedIdea && (
        <div className="opacity-0 animate-fade-in-up" style={{ animationFillMode: "forwards" }}>
          <p className="text-xs font-mono tracking-widest uppercase text-indigo-400/60 mb-4">
            Step 2 / 4
          </p>
          <h2 className="text-3xl md:text-4xl font-light tracking-tight text-white mb-8" style={{ fontFamily: "'Fraunces', serif" }}>
            {language === "fr" ? "Personnalisez votre livre" : "Customize your book"}
          </h2>

          <Card className="rounded-xl border border-white/5 bg-[#121212]/50 p-8 mb-8" data-testid="customize-card">
            <div className="space-y-6">
              <div>
                <label className="text-xs font-mono tracking-widest uppercase text-white/40 mb-2 block">
                  {language === "fr" ? "Titre" : "Title"}
                </label>
                <Input
                  value={selectedIdea.title}
                  onChange={(e) => setSelectedIdea({ ...selectedIdea, title: e.target.value })}
                  className="bg-black/20 border-white/10 h-12 text-lg"
                  data-testid="book-title-input"
                />
              </div>
              <div>
                <label className="text-xs font-mono tracking-widest uppercase text-white/40 mb-2 block">
                  {language === "fr" ? "Sous-titre" : "Subtitle"}
                </label>
                <Input
                  value={selectedIdea.subtitle || ""}
                  onChange={(e) => setSelectedIdea({ ...selectedIdea, subtitle: e.target.value })}
                  className="bg-black/20 border-white/10 h-12"
                  data-testid="book-subtitle-input"
                />
              </div>
              <div>
                <label className="text-xs font-mono tracking-widest uppercase text-white/40 mb-2 block">
                  Description
                </label>
                <Textarea
                  value={selectedIdea.description}
                  onChange={(e) => setSelectedIdea({ ...selectedIdea, description: e.target.value })}
                  className="bg-black/20 border-white/10 min-h-[120px]"
                  data-testid="book-description-input"
                />
              </div>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="text-xs font-mono tracking-widest uppercase text-white/40 mb-2 block">
                    {language === "fr" ? "Source des images" : "Image source"}
                  </label>
                  <Select value={imageSource} onValueChange={setImageSource}>
                    <SelectTrigger className="bg-black/20 border-white/10 h-12" data-testid="image-source-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ai">AI (Nano Banana)</SelectItem>
                      <SelectItem value="stock">Stock (Unsplash)</SelectItem>
                      <SelectItem value="both">Both</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-xs font-mono tracking-widest uppercase text-white/40 mb-2 block">
                    {language === "fr" ? "Pages cibles" : "Target pages"}
                  </label>
                  <Input
                    type="number"
                    value={selectedIdea.estimated_pages || 100}
                    onChange={(e) => setSelectedIdea({ ...selectedIdea, estimated_pages: parseInt(e.target.value) || 100 })}
                    className="bg-black/20 border-white/10 h-12"
                    data-testid="target-pages-input"
                  />
                </div>
              </div>
            </div>
          </Card>

          <div className="flex gap-4">
            <Button
              variant="outline"
              onClick={() => setStep(0)}
              className="border-white/10 text-white/60 hover:bg-white/5 h-12 px-6"
              data-testid="back-to-ideas-btn"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              {language === "fr" ? "Retour" : "Back"}
            </Button>
            <Button
              onClick={handleCreateBook}
              disabled={loading}
              data-testid="create-book-btn"
              className="bg-indigo-500 hover:bg-indigo-600 text-white h-12 px-8 glow-button"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  {language === "fr" ? "Creation en cours..." : "Creating..."}
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 mr-2" />
                  {language === "fr" ? "Creer et generer le plan" : "Create & generate outline"}
                </>
              )}
            </Button>
          </div>
        </div>
      )}

      {/* Step 2: Outline */}
      {step === 2 && (
        <div className="opacity-0 animate-fade-in-up" style={{ animationFillMode: "forwards" }}>
          <p className="text-xs font-mono tracking-widest uppercase text-indigo-400/60 mb-4">
            Step 3 / 4
          </p>
          <h2 className="text-3xl md:text-4xl font-light tracking-tight text-white mb-8" style={{ fontFamily: "'Fraunces', serif" }}>
            {language === "fr" ? "Validez le plan du livre" : "Review the book outline"}
          </h2>

          <div className="space-y-4 mb-8" data-testid="outline-list">
            {outline.map((ch, i) => (
              <Card
                key={i}
                className="rounded-xl border border-white/5 bg-[#121212]/50 p-5"
                data-testid={`outline-chapter-${ch.chapter_number}`}
              >
                <div className="flex items-start gap-4">
                  <div className="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center flex-shrink-0 mt-1">
                    <span className="text-sm font-mono text-indigo-400">{ch.chapter_number}</span>
                  </div>
                  <div className="flex-1">
                    <h4 className="text-white font-medium mb-1">{ch.title}</h4>
                    <p className="text-white/40 text-sm mb-2">{ch.summary}</p>
                    <div className="flex flex-wrap gap-1">
                      {ch.key_points?.map((kp, j) => (
                        <Badge key={j} variant="outline" className="text-[10px] text-white/30 border-white/10">
                          {kp}
                        </Badge>
                      ))}
                    </div>
                    <p className="text-[10px] font-mono text-white/20 mt-2">
                      ~{ch.estimated_pages} pages
                    </p>
                  </div>
                </div>
              </Card>
            ))}
          </div>

          <div className="flex gap-4">
            <Button
              variant="outline"
              onClick={() => setStep(1)}
              className="border-white/10 text-white/60 hover:bg-white/5 h-12 px-6"
              data-testid="back-to-customize-btn"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              {language === "fr" ? "Retour" : "Back"}
            </Button>
            <Button
              onClick={handleApproveOutline}
              disabled={loading}
              data-testid="approve-outline-btn"
              className="bg-indigo-500 hover:bg-indigo-600 text-white h-12 px-8 glow-button"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Check className="w-4 h-4 mr-2" />
              )}
              {language === "fr" ? "Approuver et ecrire le livre" : "Approve & write book"}
            </Button>
          </div>
        </div>
      )}

      {/* Step 3: Writing Progress */}
      {step === 3 && (
        <div className="opacity-0 animate-fade-in-up" style={{ animationFillMode: "forwards" }}>
          <p className="text-xs font-mono tracking-widest uppercase text-indigo-400/60 mb-4">
            Step 4 / 4
          </p>
          <h2 className="text-3xl md:text-4xl font-light tracking-tight text-white mb-8" style={{ fontFamily: "'Fraunces', serif" }}>
            {language === "fr" ? "Ecriture en cours..." : "Writing in progress..."}
          </h2>

          <Card className="rounded-xl border border-white/5 bg-[#121212]/50 p-8" data-testid="writing-progress-card">
            <div className="flex items-center gap-4 mb-6">
              <div className="w-12 h-12 rounded-xl bg-indigo-500/20 flex items-center justify-center">
                <PenTool className="w-5 h-5 text-indigo-400 animate-pulse" />
              </div>
              <div>
                <h3 className="text-white text-lg font-medium" style={{ fontFamily: "'Fraunces', serif" }}>
                  {writingProgress
                    ? `${writingProgress.generated_chapters} / ${writingProgress.total_chapters} ${language === "fr" ? "chapitres" : "chapters"}`
                    : language === "fr" ? "Demarrage de l'ecriture..." : "Starting writing..."}
                </h3>
                <p className="text-white/40 text-sm">
                  {writingProgress?.status === "error"
                    ? writingProgress.error
                    : language === "fr"
                    ? "L'IA ecrit votre livre chapitre par chapitre..."
                    : "AI is writing your book chapter by chapter..."}
                </p>
              </div>
            </div>

            {writingProgress && (
              <>
                <Progress
                  value={(writingProgress.generated_chapters / Math.max(writingProgress.total_chapters, 1)) * 100}
                  className="h-2 mb-6"
                  data-testid="writing-progress-bar"
                />
                <div className="space-y-2">
                  {writingProgress.chapter_titles?.map((ch, i) => (
                    <div key={i} className="flex items-center gap-3 text-sm">
                      <Check className="w-4 h-4 text-emerald-400" />
                      <span className="text-white/60">
                        Ch. {ch.number}: {ch.title}
                      </span>
                      {ch.has_image && <ImageIcon className="w-3 h-3 text-indigo-400" />}
                    </div>
                  ))}
                </div>
              </>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
