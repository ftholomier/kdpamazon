import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  BookOpen, Download, Loader2, ArrowLeft, Eye, Image as ImageIcon,
  FileText, ChevronDown, ChevronUp, CheckCircle, PenTool, Trash2, RefreshCw
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import {
  getBook, getBookProgress, generateChapter, generateChapterImage,
  deleteChapterImage, exportBook
} from "@/lib/api";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function getImageSrc(imageUrl) {
  if (!imageUrl) return null;
  if (imageUrl.startsWith("/api")) return `${BACKEND_URL}${imageUrl}`;
  return imageUrl;
}

export default function BookDetail() {
  const { bookId } = useParams();
  const navigate = useNavigate();
  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [generatingChapter, setGeneratingChapter] = useState(null);
  const [generatingImage, setGeneratingImage] = useState(null);
  const [deletingImage, setDeletingImage] = useState(null);
  const [expandedChapter, setExpandedChapter] = useState(null);
  const [previewMode, setPreviewMode] = useState(false);

  const fetchBook = useCallback(async () => {
    try {
      const data = await getBook(bookId);
      setBook(data);
    } catch (err) {
      toast.error("Failed to load book");
      navigate("/library");
    } finally {
      setLoading(false);
    }
  }, [bookId, navigate]);

  useEffect(() => {
    fetchBook();
  }, [fetchBook]);

  useEffect(() => {
    if (!book || book.status !== "writing") return;
    const interval = setInterval(async () => {
      try {
        const progress = await getBookProgress(bookId);
        if (progress.status !== "writing") {
          clearInterval(interval);
          fetchBook();
        }
      } catch (err) {}
    }, 5000);
    return () => clearInterval(interval);
  }, [book, bookId, fetchBook]);

  const handleGenerateChapter = async (chapterNum) => {
    setGeneratingChapter(chapterNum);
    try {
      await generateChapter(bookId, chapterNum);
      await fetchBook();
      toast.success(`Chapter ${chapterNum} generated!`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to generate chapter");
    } finally {
      setGeneratingChapter(null);
    }
  };

  const handleGenerateImage = async (chapterNum) => {
    setGeneratingImage(chapterNum);
    try {
      const result = await generateChapterImage(bookId, chapterNum);
      if (result.image_url) {
        await fetchBook();
        toast.success(`Image generated for chapter ${chapterNum}!`);
      } else {
        toast.error("No image could be generated");
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to generate image");
    } finally {
      setGeneratingImage(null);
    }
  };

  const handleDeleteImage = async (chapterNum) => {
    setDeletingImage(chapterNum);
    try {
      await deleteChapterImage(bookId, chapterNum);
      await fetchBook();
      toast.success("Image removed");
    } catch (err) {
      toast.error("Failed to delete image");
    } finally {
      setDeletingImage(null);
    }
  };

  const handleExport = async (format) => {
    setExporting(true);
    try {
      const response = await exportBook(bookId, format);
      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${book.title.replace(/\s+/g, "_")}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Exported as ${format.toUpperCase()}!`);
    } catch (err) {
      toast.error(`Export failed: ${err.message}`);
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
      </div>
    );
  }

  if (!book) return null;

  const chapters = (book.chapters || []).sort((a, b) => a.chapter_number - b.chapter_number);
  const outline = book.outline || [];
  const progress = chapters.length / Math.max(outline.length, 1);
  const is_fr = book.language === "fr";

  // Book preview mode
  if (previewMode) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] p-8" data-testid="book-preview-page">
        <div className="max-w-3xl mx-auto">
          <Button
            variant="ghost"
            onClick={() => setPreviewMode(false)}
            className="mb-8 text-white/50 hover:text-white"
            data-testid="exit-preview-btn"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            {is_fr ? "Quitter l'apercu" : "Exit Preview"}
          </Button>

          <div className="book-page rounded-lg p-12 shadow-2xl mb-8" data-testid="book-preview-title-page">
            <div className="text-center py-20">
              <h1 className="text-3xl font-bold text-gray-900 mb-4" style={{ fontFamily: "'Fraunces', serif" }}>
                {book.title}
              </h1>
              {book.subtitle && (
                <p className="text-lg text-gray-600">{book.subtitle}</p>
              )}
            </div>
          </div>

          {chapters.map((ch) => (
            <div
              key={ch.chapter_number}
              className="book-page rounded-lg p-12 shadow-2xl mb-4"
              data-testid={`preview-chapter-${ch.chapter_number}`}
            >
              <p className="text-xs uppercase tracking-widest text-gray-400 mb-2">
                {is_fr ? `Chapitre ${ch.chapter_number}` : `Chapter ${ch.chapter_number}`}
              </p>
              <h1 className="text-2xl font-bold text-gray-900 mb-6" style={{ fontFamily: "'Fraunces', serif" }}>
                {ch.title}
              </h1>
              {ch.image_url && (
                <div className="mb-6 flex justify-center">
                  <img
                    src={getImageSrc(ch.image_url)}
                    alt={ch.title}
                    className="max-w-full h-auto rounded-lg max-h-64 object-cover"
                  />
                </div>
              )}
              <div className="prose">
                {ch.content?.split("\n").map((line, i) => {
                  const trimmed = line.trim();
                  if (!trimmed) return <br key={i} />;
                  if (/^#{1,4}\s/.test(trimmed)) {
                    const level = trimmed.match(/^(#{1,4})/)[1].length;
                    const text = trimmed.replace(/^#{1,4}\s+/, "");
                    const sizes = { 1: "text-2xl", 2: "text-xl", 3: "text-lg", 4: "text-base" };
                    return <h2 key={i} className={`${sizes[level] || "text-lg"} font-semibold text-gray-800 mt-6 mb-3`} style={{ fontFamily: "'Fraunces', serif" }}>{text}</h2>;
                  }
                  if (/^[-*]\s/.test(trimmed)) {
                    return <li key={i} className="text-gray-700 ml-6 list-disc">{trimmed.replace(/^[-*]\s+/, "")}</li>;
                  }
                  if (/^\d+[.)]\s/.test(trimmed)) {
                    return <li key={i} className="text-gray-700 ml-6 list-decimal">{trimmed.replace(/^\d+[.)]\s+/, "")}</li>;
                  }
                  // Parse inline bold/italic
                  const html = trimmed
                    .replace(/\*{3}(.+?)\*{3}/g, "<strong><em>$1</em></strong>")
                    .replace(/\*{2}(.+?)\*{2}/g, "<strong>$1</strong>")
                    .replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");
                  return <p key={i} className="text-gray-700 leading-relaxed mb-3 text-justify" dangerouslySetInnerHTML={{ __html: html }} />;
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 lg:p-12 max-w-5xl mx-auto" data-testid="book-detail-page">
      {/* Header */}
      <div className="flex items-start justify-between mb-12">
        <div className="opacity-0 animate-fade-in-up" style={{ animationFillMode: "forwards" }}>
          <Button
            variant="ghost"
            onClick={() => navigate("/library")}
            className="mb-4 text-white/40 hover:text-white -ml-4"
            data-testid="back-to-library-btn"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Library
          </Button>
          <h1 className="text-4xl font-light tracking-tight text-white leading-tight mb-2" style={{ fontFamily: "'Fraunces', serif" }}>
            {book.title}
          </h1>
          {book.subtitle && (
            <p className="text-lg text-white/50">{book.subtitle}</p>
          )}
          <div className="flex items-center gap-3 mt-4">
            <Badge variant="outline" className="text-xs font-mono text-indigo-400 border-indigo-500/30">
              {book.category}
            </Badge>
            <Badge variant="outline" className="text-xs font-mono text-white/40 border-white/10">
              {book.language === "fr" ? "FR" : "EN"}
            </Badge>
            <Badge variant="outline" className="text-xs font-mono text-white/40 border-white/10">
              {chapters.length} / {outline.length} {is_fr ? "chapitres" : "chapters"}
            </Badge>
          </div>
        </div>

        <div className="flex gap-3 opacity-0 animate-fade-in-up animate-stagger-1" style={{ animationFillMode: "forwards" }}>
          {chapters.length > 0 && (
            <>
              <Button
                variant="outline"
                onClick={() => setPreviewMode(true)}
                data-testid="preview-book-btn"
                className="border-white/10 text-white/60 hover:bg-white/5 h-10"
              >
                <Eye className="w-4 h-4 mr-2" />
                {is_fr ? "Apercu" : "Preview"}
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    disabled={exporting}
                    data-testid="export-book-btn"
                    className="bg-indigo-500 hover:bg-indigo-600 text-white h-10 glow-button"
                  >
                    {exporting ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <Download className="w-4 h-4 mr-2" />
                    )}
                    Export KDP
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem onClick={() => handleExport("pdf")} data-testid="export-pdf-btn">
                    <FileText className="w-4 h-4 mr-2" /> PDF (KDP Ready)
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleExport("docx")} data-testid="export-docx-btn">
                    <FileText className="w-4 h-4 mr-2" /> DOCX
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleExport("epub")} data-testid="export-epub-btn">
                    <BookOpen className="w-4 h-4 mr-2" /> EPUB
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          )}
        </div>
      </div>

      {/* Progress */}
      {outline.length > 0 && (
        <Card className="rounded-xl border border-white/5 bg-[#121212]/50 p-6 mb-8" data-testid="book-progress-card">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-white/60">{is_fr ? "Progression de l'ecriture" : "Writing Progress"}</span>
            <span className="text-sm font-mono text-indigo-400">{Math.round(progress * 100)}%</span>
          </div>
          <Progress value={progress * 100} className="h-2" />
        </Card>
      )}

      {/* Chapters */}
      <div className="space-y-3" data-testid="chapters-list">
        {outline.map((outlineCh) => {
          const chapter = chapters.find((c) => c.chapter_number === outlineCh.chapter_number);
          const isExpanded = expandedChapter === outlineCh.chapter_number;
          const isGenerated = !!chapter;
          const hasImage = chapter?.image_url;

          return (
            <Card
              key={outlineCh.chapter_number}
              className="rounded-xl border border-white/5 bg-[#121212]/50 overflow-hidden"
              data-testid={`chapter-item-${outlineCh.chapter_number}`}
            >
              {/* Chapter header row */}
              <div
                className="flex items-center justify-between p-5 cursor-pointer hover:bg-white/[0.02] transition-colors"
                onClick={() => setExpandedChapter(isExpanded ? null : outlineCh.chapter_number)}
              >
                <div className="flex items-center gap-4">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${isGenerated ? "bg-emerald-500/10" : "bg-white/5"}`}>
                    {isGenerated ? (
                      <CheckCircle className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <span className="text-xs font-mono text-white/30">{outlineCh.chapter_number}</span>
                    )}
                  </div>
                  <div className="flex-1">
                    <h4 className="text-white text-sm font-medium">{outlineCh.title}</h4>
                    <p className="text-white/30 text-xs">~{outlineCh.estimated_pages} pages</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {/* Show image thumbnail inline */}
                  {hasImage && (
                    <img
                      src={getImageSrc(chapter.image_url)}
                      alt=""
                      className="w-10 h-10 rounded object-cover border border-white/10"
                    />
                  )}
                  {isGenerated && !hasImage && (
                    <span className="text-[10px] text-white/20 font-mono">{is_fr ? "pas d'image" : "no image"}</span>
                  )}
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-white/30" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-white/30" />
                  )}
                </div>
              </div>

              {/* Expanded content */}
              {isExpanded && (
                <div className="border-t border-white/5 p-5">
                  {isGenerated ? (
                    <>
                      {/* Image section - visible in interface */}
                      {hasImage && (
                        <div className="mb-6 p-4 rounded-lg bg-black/30 border border-white/5" data-testid={`chapter-image-${outlineCh.chapter_number}`}>
                          <div className="flex items-start gap-4">
                            <img
                              src={getImageSrc(chapter.image_url)}
                              alt={chapter.title}
                              className="w-48 h-32 rounded-lg object-cover border border-white/10"
                            />
                            <div className="flex-1">
                              <p className="text-xs font-mono text-white/40 mb-3">
                                {is_fr ? "Illustration du chapitre" : "Chapter illustration"}
                              </p>
                              <div className="flex gap-2">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={(e) => { e.stopPropagation(); handleGenerateImage(outlineCh.chapter_number); }}
                                  disabled={generatingImage === outlineCh.chapter_number}
                                  data-testid={`regenerate-image-ch-${outlineCh.chapter_number}`}
                                  className="border-white/10 text-white/50 hover:bg-white/5 text-xs"
                                >
                                  {generatingImage === outlineCh.chapter_number ? (
                                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                                  ) : (
                                    <RefreshCw className="w-3 h-3 mr-1" />
                                  )}
                                  {is_fr ? "Nouvelle image" : "New image"}
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={(e) => { e.stopPropagation(); handleDeleteImage(outlineCh.chapter_number); }}
                                  disabled={deletingImage === outlineCh.chapter_number}
                                  data-testid={`delete-image-ch-${outlineCh.chapter_number}`}
                                  className="border-white/10 text-red-400/60 hover:bg-red-500/10 hover:text-red-400 text-xs"
                                >
                                  {deletingImage === outlineCh.chapter_number ? (
                                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                                  ) : (
                                    <Trash2 className="w-3 h-3 mr-1" />
                                  )}
                                  {is_fr ? "Supprimer" : "Delete"}
                                </Button>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Chapter content preview */}
                      <ScrollArea className="max-h-96 mb-4">
                        <div className="prose prose-sm prose-invert max-w-none">
                          {chapter.content?.split("\n").slice(0, 30).map((line, i) => {
                            const trimmed = line.trim();
                            if (!trimmed) return <br key={i} />;
                            if (/^#{1,4}\s/.test(trimmed)) {
                              const text = trimmed.replace(/^#{1,4}\s+/, "");
                              return <h3 key={i} className="text-white/80 text-sm font-semibold mt-4 mb-2">{text}</h3>;
                            }
                            if (/^[-*]\s/.test(trimmed)) {
                              return <li key={i} className="text-white/50 text-sm ml-4 list-disc">{trimmed.replace(/^[-*]\s+/, "")}</li>;
                            }
                            // Clean inline markdown for display
                            const cleaned = trimmed
                              .replace(/\*{2,3}(.+?)\*{2,3}/g, "$1")
                              .replace(/\*(.+?)\*/g, "$1");
                            return <p key={i} className="text-white/50 text-sm leading-relaxed mb-2">{cleaned}</p>;
                          })}
                          {chapter.content?.split("\n").length > 30 && (
                            <p className="text-indigo-400 text-sm mt-4">
                              {is_fr ? "... cliquez sur Apercu pour lire le chapitre complet" : "... click Preview to read full chapter"}
                            </p>
                          )}
                        </div>
                      </ScrollArea>

                      {/* Generate image button if no image */}
                      {!hasImage && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleGenerateImage(outlineCh.chapter_number)}
                          disabled={generatingImage === outlineCh.chapter_number}
                          data-testid={`generate-image-ch-${outlineCh.chapter_number}`}
                          className="border-white/10 text-white/60 hover:bg-white/5"
                        >
                          {generatingImage === outlineCh.chapter_number ? (
                            <Loader2 className="w-3 h-3 mr-2 animate-spin" />
                          ) : (
                            <ImageIcon className="w-3 h-3 mr-2" />
                          )}
                          {is_fr ? "Generer une image" : "Generate Image"}
                        </Button>
                      )}
                    </>
                  ) : (
                    <div className="text-center py-6">
                      <p className="text-white/30 text-sm mb-4">{outlineCh.summary}</p>
                      <Button
                        onClick={() => handleGenerateChapter(outlineCh.chapter_number)}
                        disabled={generatingChapter === outlineCh.chapter_number}
                        data-testid={`generate-chapter-${outlineCh.chapter_number}`}
                        className="bg-indigo-500/80 hover:bg-indigo-600 text-white text-sm"
                      >
                        {generatingChapter === outlineCh.chapter_number ? (
                          <>
                            <Loader2 className="w-3 h-3 mr-2 animate-spin" />
                            {is_fr ? "Generation..." : "Generating..."}
                          </>
                        ) : (
                          <>
                            <PenTool className="w-3 h-3 mr-2" />
                            {is_fr ? "Generer le chapitre" : "Generate Chapter"}
                          </>
                        )}
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
