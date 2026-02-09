# Lumina Press - KDP Book Creator PRD

## Problem Statement
Application interfacee avec Gemini 2.5 Flash pour detecter des thematiques de livres sur Amazon, proposer des idees, ecrire le livre (~100 pages), le mettre en page avec photos, et l'exporter au format KDP (PDF/DOCX/EPUB).

## Architecture
- **Frontend**: React + Tailwind + Shadcn/UI (dark theme "Nocturnal Editor")
- **Backend**: FastAPI + MongoDB + emergentintegrations (Gemini 2.5 Flash)
- **AI**: Gemini 2.5 Flash (text), Gemini Nano Banana (images), Unsplash/Picsum (stock)
- **Export**: reportlab (PDF), python-docx (DOCX), ebooklib (EPUB)

## User Personas
- Self-publishers wanting to create KDP books quickly
- Content creators exploring trending niches
- Entrepreneurs building passive income via KDP

## Core Requirements
1. Theme discovery (AI-powered Amazon trend analysis)
2. Book idea generation (5 ideas per theme)
3. Full book writing pipeline (outline -> chapters -> images -> export)
4. KDP-compliant exports (PDF/DOCX/EPUB with page numbers, TOC)
5. Bilingual support (FR/EN)
6. API key flexibility (Emergent universal key or custom Google key)
7. Image source choice (AI Nano Banana / Stock / Both)

## What's Been Implemented (Feb 9, 2026)
- Full-stack app with React frontend + FastAPI backend
- Theme discovery with Gemini 2.5 Flash
- Book idea generation
- Book creation pipeline (create -> outline -> chapters -> images -> export)
- All 3 export formats (PDF/DOCX/EPUB) with proper markdown parsing
- Page numbers in PDF and DOCX
- Table of contents with chapter references
- Stock image support (Unsplash + Lorem Picsum fallback)
- AI image generation (Gemini Nano Banana)
- Image management (view, regenerate, delete per chapter)
- Book deletion with cleanup
- Settings page (API key, image source, language)
- Dark theme Lumina Press branding

## Bug Fixes (Feb 9, 2026)
- Fixed book deletion (now cleans up images + export files)
- Fixed stock image generation (Unsplash source URLs, Picsum fallback)
- Added image visibility in chapter interface (not just preview)
- Added regenerate/delete image buttons per chapter
- Fixed markdown formatting in all exports (### *** no longer visible)
- Added page numbers to PDF and DOCX
- Added auto-generated TOC

## Prioritized Backlog
### P0
- [x] Core book creation flow
- [x] All export formats
- [x] Markdown parsing in exports

### P1
- [ ] Cover image generation for KDP
- [ ] Batch chapter generation with progress bar
- [ ] Better TOC with exact page numbers (2-pass PDF build)

### P2
- [ ] Book template system (preset layouts for different categories)
- [ ] Custom fonts in exports
- [ ] Book metadata editor (ISBN, author bio, back cover text)
- [ ] Multi-book series support
- [ ] Revenue tracking integration

## Next Tasks
1. Cover image generation for the book (KDP front cover)
2. Exact page numbers in PDF TOC (2-pass rendering)
3. Book templates per category
4. Author profile / branding settings
