import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const api = axios.create({ baseURL: API });

// Settings
export const getSettings = () => api.get("/settings").then(r => r.data);
export const updateSettings = (data) => api.put("/settings", data).then(r => r.data);

// Themes
export const discoverThemes = (data) => api.post("/themes/discover", data).then(r => r.data);

// Ideas
export const generateIdeas = (data) => api.post("/ideas/generate", data).then(r => r.data);

// Books
export const createBook = (data) => api.post("/books/create", data).then(r => r.data);
export const getBooks = () => api.get("/books").then(r => r.data);
export const getBook = (id) => api.get(`/books/${id}`).then(r => r.data);
export const deleteBook = (id) => api.delete(`/books/${id}`).then(r => r.data);
export const getBookProgress = (id) => api.get(`/books/${id}/progress`).then(r => r.data);

// Book Generation
export const generateOutline = (bookId) => api.post(`/books/${bookId}/generate-outline`).then(r => r.data);
export const updateOutline = (bookId, outline) => api.put(`/books/${bookId}/outline`, { book_id: bookId, outline }).then(r => r.data);
export const generateChapter = (bookId, chapterNum) => api.post(`/books/${bookId}/generate-chapter/${chapterNum}`).then(r => r.data);
export const generateAllChapters = (bookId) => api.post(`/books/${bookId}/generate-all-chapters`).then(r => r.data);
export const generateChapterImage = (bookId, chapterNum) => api.post(`/books/${bookId}/generate-image/${chapterNum}`).then(r => r.data);

// Export
export const exportBook = (bookId, format) => 
  api.post(`/books/${bookId}/export`, { book_id: bookId, format }, { responseType: 'blob' }).then(r => r);

export default api;
