import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  BookOpen, Download, Loader2, ArrowLeft, Eye, Image as ImageIcon,
  FileText, ChevronDown, ChevronUp, CheckCircle, Clock, PenTool
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
  getBook, getBookProgress, generateChapter, generateChapterImage, exportBook
} from "@/lib/api";

export default function BookDetail() {
  const { bookId } = useParams();
  const navigate = useNavigate();
  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [generatingChapter, setGeneratingChapter] = useState(null);
  const [generatingImage, setGeneratingImage] = useState(null);
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

  // Poll progress if writing
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
            Exit Preview
          </Button>

          {/* Book pages */}
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
              <h1 className="text-2xl font-bold text-gray-900 mb-6" style={{ fontFamily: "'Fraunces', serif" }}>
                {book.language === "fr" ? `Chapitre ${ch.chapter_number}` : `Chapter ${ch.chapter_number}`}: {ch.title}
              </h1>
              {ch.image_url && (
                <div className="mb-6 flex justify-center">
                  <img
                    src={ch.image_url.startsWith("/api") ? `${process.env.REACT_APP_BACKEND_URL}${ch.image_url}` : ch.image_url}
                    alt={ch.title}
                    className="max-w-full h-auto rounded-lg max-h-64 object-cover"
                  />
                </div>
              )}
              <div className="prose">
                {ch.content?.split("\n").map((line, i) => {
                  const trimmed = line.trim();
                  if (!trimmed) return <br key={i} />;
                  if (trimmed.startsWith("## ")) return <h2 key={i} className="text-xl font-semibold text-gray-800 mt-6 mb-3" style={{ fontFamily: "'Fraunces', serif" }}>{trimmed.slice(3)}</h2>;
                  if (trimmed.startsWith("# ")) return <h1 key={i} className="text-2xl font-bold text-gray-900 mt-8 mb-4" style={{ fontFamily: "'Fraunces', serif" }}>{trimmed.slice(2)}</h1>;
                  return <p key={i} className="text-gray-700 leading-relaxed mb-3 text-justify">{trimmed}</p>;
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
              {chapters.length} / {outline.length} chapters
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
                Preview
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
            <span className="text-sm text-white/60">Writing Progress</span>
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

          return (
            <Card
              key={outlineCh.chapter_number}
              className="rounded-xl border border-white/5 bg-[#121212]/50 overflow-hidden"
              data-testid={`chapter-item-${outlineCh.chapter_number}`}
            >
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
                  <div>
                    <h4 className="text-white text-sm font-medium">{outlineCh.title}</h4>
                    <p className="text-white/30 text-xs">~{outlineCh.estimated_pages} pages</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {chapter?.image_url && (
                    <ImageIcon className="w-4 h-4 text-indigo-400" />
                  )}
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-white/30" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-white/30" />
                  )}
                </div>
              </div>

              {isExpanded && (
                <div className="border-t border-white/5 p-5">
                  {isGenerated ? (
                    <>
                      <ScrollArea className="max-h-96 mb-4">
                        <div className="prose prose-sm prose-invert max-w-none">
                          {chapter.content?.split("\n").slice(0, 30).map((line, i) => {
                            const trimmed = line.trim();
                            if (!trimmed) return <br key={i} />;
                            if (trimmed.startsWith("## ")) return <h3 key={i} className="text-white/80 text-sm font-semibold mt-4 mb-2">{trimmed.slice(3)}</h3>;
                            return <p key={i} className="text-white/50 text-sm leading-relaxed mb-2">{trimmed}</p>;
                          })}
                          {chapter.content?.split("\n").length > 30 && (
                            <p className="text-indigo-400 text-sm mt-4">... click Preview to read full chapter</p>
                          )}
                        </div>
                      </ScrollArea>
                      {!chapter.image_url && (
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
                          Generate Image
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
                            Generating...
                          </>
                        ) : (
                          <>
                            <PenTool className="w-3 h-3 mr-2" />
                            Generate Chapter
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

// Import at top is missing PenTool - add it
