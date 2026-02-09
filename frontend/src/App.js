import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import Sidebar from "@/components/Sidebar";
import Dashboard from "@/pages/Dashboard";
import BookCreator from "@/pages/BookCreator";
import Library from "@/pages/Library";
import Settings from "@/pages/Settings";
import BookDetail from "@/pages/BookDetail";
import "@/App.css";

function App() {
  return (
    <div className="noise-bg min-h-screen bg-background">
      <BrowserRouter>
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 ml-64 min-h-screen">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/create" element={<BookCreator />} />
              <Route path="/library" element={<Library />} />
              <Route path="/book/:bookId" element={<BookDetail />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
      <Toaster 
        theme="dark" 
        position="bottom-right"
        toastOptions={{
          style: {
            background: 'hsl(0 0% 7%)',
            border: '1px solid rgba(255,255,255,0.1)',
            color: '#ededed'
          }
        }}
      />
    </div>
  );
}

export default App;
