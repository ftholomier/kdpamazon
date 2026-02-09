import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { BookOpen, Trash2, Eye, Loader2, Clock, CheckCircle, AlertCircle, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getBooks, deleteBook } from "@/lib/api";

const statusConfig = {
  outline_pending: { label: "Outline Pending", color: "text-amber-400 bg-amber-500/10 border-amber-500/20", icon: Clock },
  outline_ready: { label: "Outline Ready", color: "text-blue-400 bg-blue-500/10 border-blue-500/20", icon: FileText },
  outline_approved: { label: "Approved", color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20", icon: CheckCircle },
  writing: { label: "Writing...", color: "text-purple-400 bg-purple-500/10 border-purple-500/20", icon: Loader2 },
  chapters_complete: { label: "Complete", color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20", icon: CheckCircle },
  error: { label: "Error", color: "text-red-400 bg-red-500/10 border-red-500/20", icon: AlertCircle },
};

export default function Library() {
  const navigate = useNavigate();
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBooks();
  }, []);

  const fetchBooks = async () => {
    try {
      const data = await getBooks();
      setBooks(data.books || []);
    } catch (err) {
      toast.error("Failed to load library");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e, bookId) => {
    e.stopPropagation();
    if (!window.confirm("Delete this book?")) return;
    try {
      await deleteBook(bookId);
      setBooks(books.filter((b) => b.id !== bookId));
      toast.success("Book deleted");
    } catch (err) {
      toast.error("Failed to delete book");
    }
  };

  return (
    <div className="p-8 lg:p-12 max-w-7xl mx-auto" data-testid="library-page">
      <div className="mb-12 opacity-0 animate-fade-in-up" style={{ animationFillMode: "forwards" }}>
        <p className="text-xs font-mono tracking-widest uppercase text-indigo-400/60 mb-4">
          Your Collection
        </p>
        <h1 className="text-5xl md:text-6xl font-light tracking-tight text-white leading-none mb-4" style={{ fontFamily: "'Fraunces', serif" }}>
          <span className="gradient-text">Library</span>
        </h1>
        <p className="text-lg text-white/50">
          {books.length} {books.length === 1 ? "book" : "books"} in your collection
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24" data-testid="library-loading">
          <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
        </div>
      ) : books.length === 0 ? (
        <div className="text-center py-24" data-testid="library-empty">
          <div className="w-20 h-20 rounded-2xl bg-indigo-500/10 flex items-center justify-center mx-auto mb-6">
            <BookOpen className="w-8 h-8 text-indigo-400/60" />
          </div>
          <h3 className="text-xl text-white/60 mb-2" style={{ fontFamily: "'Fraunces', serif" }}>
            No books yet
          </h3>
          <p className="text-white/30 text-sm mb-6">Start creating your first book</p>
          <Button
            onClick={() => navigate("/create")}
            data-testid="create-first-book-btn"
            className="bg-indigo-500 hover:bg-indigo-600 text-white glow-button"
          >
            Create a Book
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="books-grid">
          {books.map((book, i) => {
            const status = statusConfig[book.status] || statusConfig.outline_pending;
            const StatusIcon = status.icon;
            return (
              <Card
                key={book.id}
                data-testid={`book-card-${book.id}`}
                onClick={() => navigate(`/book/${book.id}`)}
                className="group rounded-xl border border-white/5 bg-[#121212]/50 hover:border-indigo-500/30 transition-all duration-500 cursor-pointer overflow-hidden opacity-0 animate-fade-in-up"
                style={{ animationFillMode: "forwards", animationDelay: `${i * 0.08}s` }}
              >
                {/* Cover placeholder */}
                <div className="h-32 bg-gradient-to-br from-indigo-900/20 to-purple-900/20 flex items-center justify-center border-b border-white/5">
                  <BookOpen className="w-10 h-10 text-indigo-400/30" />
                </div>
                
                <div className="p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <Badge variant="outline" className={`text-[10px] font-mono ${status.color}`}>
                      <StatusIcon className={`w-3 h-3 mr-1 ${book.status === "writing" ? "animate-spin" : ""}`} />
                      {status.label}
                    </Badge>
                    <Badge variant="outline" className="text-[10px] font-mono text-white/30 border-white/10">
                      {book.language === "fr" ? "FR" : "EN"}
                    </Badge>
                  </div>
                  
                  <h3 className="text-white font-medium mb-1 group-hover:text-indigo-300 transition-colors line-clamp-2" style={{ fontFamily: "'Fraunces', serif" }}>
                    {book.title}
                  </h3>
                  {book.subtitle && (
                    <p className="text-white/40 text-sm mb-2 line-clamp-1">{book.subtitle}</p>
                  )}
                  
                  <div className="flex items-center justify-between mt-4">
                    <span className="text-[10px] font-mono text-white/20">
                      {book.chapters?.length || 0} / {book.outline?.length || 0} ch.
                    </span>
                    <div className="flex gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); navigate(`/book/${book.id}`); }}
                        data-testid={`view-book-${book.id}`}
                        className="h-8 w-8 p-0 text-white/40 hover:text-white"
                      >
                        <Eye className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => handleDelete(e, book.id)}
                        data-testid={`delete-book-${book.id}`}
                        className="h-8 w-8 p-0 text-white/40 hover:text-red-400"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
