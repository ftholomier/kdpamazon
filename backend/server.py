from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import json
import asyncio
import base64
import aiohttp
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# Ensure exports directory exists
EXPORTS_DIR = ROOT_DIR / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)
IMAGES_DIR = ROOT_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ====== MODELS ======

class SettingsUpdate(BaseModel):
    api_key_source: str = "emergent"  # "emergent" or "custom"
    custom_api_key: Optional[str] = None
    image_source: str = "ai"  # "ai" or "stock" or "both"
    language: str = "fr"  # "fr" or "en"

class ThemeRequest(BaseModel):
    category: Optional[str] = None
    language: str = "fr"

class IdeaRequest(BaseModel):
    theme: str
    language: str = "fr"

class BookCreateRequest(BaseModel):
    title: str
    subtitle: Optional[str] = None
    description: str
    category: str
    language: str = "fr"
    target_pages: int = 100
    image_source: str = "ai"

class OutlineApproveRequest(BaseModel):
    book_id: str
    outline: List[Dict[str, Any]]

class ChapterGenerateRequest(BaseModel):
    book_id: str

class ExportRequest(BaseModel):
    book_id: str
    format: str = "pdf"  # "pdf", "epub", "docx"

# ====== HELPERS ======

def get_api_key():
    """Get the appropriate API key based on settings."""
    return os.environ.get('EMERGENT_LLM_KEY', '')

async def get_settings():
    settings = await db.settings.find_one({}, {"_id": 0})
    if not settings:
        settings = {
            "api_key_source": "emergent",
            "custom_api_key": None,
            "image_source": "ai",
            "language": "fr"
        }
    return settings

async def get_active_api_key():
    settings = await get_settings()
    if settings.get("api_key_source") == "custom" and settings.get("custom_api_key"):
        return settings["custom_api_key"], "gemini"
    return os.environ.get('EMERGENT_LLM_KEY', ''), "emergent"

async def call_gemini(prompt, system_message="You are a helpful assistant.", session_id=None):
    """Call Gemini 2.5 Flash Lite via emergentintegrations."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    
    api_key, key_type = await get_active_api_key()
    if not session_id:
        session_id = str(uuid.uuid4())
    
    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system_message
    )
    
    if key_type == "gemini":
        # User's own Google key - use directly with Gemini
        chat.with_model("gemini", "gemini-2.5-flash-lite")
    else:
        # Emergent universal key - use gemini-2.5-flash (closest available)
        chat.with_model("gemini", "gemini-2.5-flash")
    
    msg = UserMessage(text=prompt)
    response = await chat.send_message(msg)
    return response

async def generate_image_ai(prompt, book_id, image_name):
    """Generate an image using Gemini Nano Banana."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    
    api_key, _ = await get_active_api_key()
    
    chat = LlmChat(
        api_key=api_key,
        session_id=str(uuid.uuid4()),
        system_message="You are an expert illustrator creating professional book illustrations."
    )
    chat.with_model("gemini", "gemini-3-pro-image-preview").with_params(modalities=["image", "text"])
    
    msg = UserMessage(text=prompt)
    text, images = await chat.send_message_multimodal_response(msg)
    
    if images:
        img_data = base64.b64decode(images[0]['data'])
        img_path = IMAGES_DIR / f"{book_id}_{image_name}.png"
        with open(img_path, "wb") as f:
            f.write(img_data)
        return str(img_path), base64.b64encode(img_data).decode('utf-8')[:50]
    return None, None

async def fetch_stock_image(query, book_id, image_name):
    """Fetch image from free stock sources and save locally."""
    import urllib.parse
    
    # Use Pixabay API (free, no auth needed for limited use)
    encoded_query = urllib.parse.quote(query)
    urls_to_try = [
        f"https://pixabay.com/api/?key=47191920-bde77e02cd09101be53e2a260&q={encoded_query}&image_type=illustration&per_page=3&safesearch=true",
        f"https://pixabay.com/api/?key=47191920-bde77e02cd09101be53e2a260&q={encoded_query}&image_type=photo&per_page=3&safesearch=true",
    ]
    
    async with aiohttp.ClientSession() as session:
        for api_url in urls_to_try:
            try:
                async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        hits = data.get("hits", [])
                        if hits:
                            img_url = hits[0].get("webformatURL") or hits[0].get("largeImageURL")
                            if img_url:
                                # Download the image locally
                                async with session.get(img_url, timeout=aiohttp.ClientTimeout(total=20)) as img_resp:
                                    if img_resp.status == 200:
                                        img_data = await img_resp.read()
                                        img_path = IMAGES_DIR / f"{book_id}_{image_name}.png"
                                        with open(img_path, "wb") as f:
                                            f.write(img_data)
                                        return f"/api/images/{book_id}_{image_name}.png"
            except Exception as e:
                logger.error(f"Stock image fetch error: {e}")
                continue
    return None

# ====== SETTINGS ROUTES ======

@api_router.get("/settings")
async def get_settings_route():
    settings = await get_settings()
    if settings.get("custom_api_key"):
        settings["custom_api_key"] = "****" + settings["custom_api_key"][-4:] if len(settings.get("custom_api_key", "")) > 4 else "****"
    return settings

@api_router.put("/settings")
async def update_settings(data: SettingsUpdate):
    update_data = data.model_dump()
    existing = await db.settings.find_one({})
    if existing:
        if update_data.get("custom_api_key") and update_data["custom_api_key"].startswith("****"):
            update_data.pop("custom_api_key")
        await db.settings.update_one({}, {"$set": update_data})
    else:
        await db.settings.insert_one(update_data)
    return {"status": "ok"}

# ====== THEMES ROUTES ======

@api_router.post("/themes/discover")
async def discover_themes(req: ThemeRequest):
    lang = req.language
    category_filter = f" in the category '{req.category}'" if req.category else ""
    
    if lang == "fr":
        prompt = f"""Tu es un expert en analyse de marché Amazon KDP. Analyse les tendances actuelles des livres non-fiction sur Amazon{category_filter}.

Retourne exactement 6 thématiques tendance sous forme de JSON. Chaque thématique doit inclure:
- "title": le nom de la thématique
- "description": une courte description (2 phrases max)
- "demand_level": "high", "medium" ou "low"
- "competition": "high", "medium" ou "low"
- "categories": liste de 2-3 sous-catégories

Concentre-toi sur les livres intemporels: guides pratiques, recettes, tutoriels, développement personnel, livres pour enfants, DIY.

Réponds UNIQUEMENT avec le JSON, sans markdown ni backticks. Format: [{{"title": "...", ...}}]"""
    else:
        prompt = f"""You are an Amazon KDP market analysis expert. Analyze current non-fiction book trends on Amazon{category_filter}.

Return exactly 6 trending themes as JSON. Each theme must include:
- "title": theme name
- "description": short description (2 sentences max)
- "demand_level": "high", "medium" or "low"
- "competition": "high", "medium" or "low"
- "categories": list of 2-3 subcategories

Focus on timeless books: practical guides, recipes, tutorials, self-help, children's books, DIY.

Respond ONLY with JSON, no markdown or backticks. Format: [{{"title": "...", ...}}]"""

    try:
        response = await call_gemini(prompt, "You are an Amazon KDP market expert. Always respond with valid JSON only.")
        # Try to parse JSON from the response
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            cleaned = cleaned.rsplit("```", 1)[0]
        themes = json.loads(cleaned)
        return {"themes": themes}
    except json.JSONDecodeError:
        logger.error(f"Failed to parse themes JSON: {response[:200]}")
        return {"themes": [], "error": "Failed to parse AI response"}
    except Exception as e:
        logger.error(f"Theme discovery error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ====== IDEAS ROUTES ======

@api_router.post("/ideas/generate")
async def generate_ideas(req: IdeaRequest):
    lang = req.language
    
    if lang == "fr":
        prompt = f"""Tu es un expert en création de livres pour Amazon KDP. Basé sur la thématique "{req.theme}", propose exactement 5 idées de livres non-fiction intemporels.

Pour chaque idée, donne:
- "title": titre accrocheur du livre
- "subtitle": sous-titre descriptif
- "description": description détaillée (3-4 phrases) expliquant le contenu et la valeur ajoutée
- "target_audience": public cible
- "estimated_pages": nombre de pages estimé (entre 80 et 120)
- "category": catégorie (guide, recette, tutoriel, développement personnel, enfants, DIY)
- "unique_angle": ce qui rend ce livre unique

Réponds UNIQUEMENT avec le JSON. Format: [{{"title": "...", ...}}]"""
    else:
        prompt = f"""You are an Amazon KDP book creation expert. Based on the theme "{req.theme}", propose exactly 5 timeless non-fiction book ideas.

For each idea, provide:
- "title": catchy book title
- "subtitle": descriptive subtitle
- "description": detailed description (3-4 sentences) explaining content and value
- "target_audience": target audience
- "estimated_pages": estimated pages (between 80 and 120)
- "category": category (guide, recipe, tutorial, self-help, children, DIY)
- "unique_angle": what makes this book unique

Respond ONLY with JSON. Format: [{{"title": "...", ...}}]"""

    try:
        response = await call_gemini(prompt, "You are a book creation expert. Always respond with valid JSON only.")
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            cleaned = cleaned.rsplit("```", 1)[0]
        ideas = json.loads(cleaned)
        return {"ideas": ideas}
    except json.JSONDecodeError:
        logger.error(f"Failed to parse ideas JSON: {response[:200]}")
        return {"ideas": [], "error": "Failed to parse AI response"}
    except Exception as e:
        logger.error(f"Ideas generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ====== BOOKS ROUTES ======

@api_router.post("/books/create")
async def create_book(req: BookCreateRequest):
    book_id = str(uuid.uuid4())
    book = {
        "id": book_id,
        "title": req.title,
        "subtitle": req.subtitle,
        "description": req.description,
        "category": req.category,
        "language": req.language,
        "target_pages": req.target_pages,
        "image_source": req.image_source,
        "status": "outline_pending",
        "outline": [],
        "chapters": [],
        "cover_image": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.books.insert_one(book)
    book.pop("_id", None)
    return book

@api_router.post("/books/{book_id}/generate-outline")
async def generate_outline(book_id: str):
    book = await db.books.find_one({"id": book_id}, {"_id": 0})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    lang = book.get("language", "fr")
    pages = book.get("target_pages", 100)
    num_chapters = max(10, pages // 6)
    
    if lang == "fr":
        prompt = f"""Tu es un auteur professionnel. Crée un plan détaillé pour le livre suivant:

Titre: {book['title']}
Sous-titre: {book.get('subtitle', '')}
Description: {book['description']}
Catégorie: {book['category']}
Nombre de pages cible: {pages}

Crée exactement {num_chapters} chapitres. Pour chaque chapitre, donne:
- "chapter_number": numéro du chapitre
- "title": titre du chapitre
- "summary": résumé du contenu (2-3 phrases)
- "key_points": liste de 3-5 points clés à couvrir
- "estimated_pages": pages estimées pour ce chapitre
- "image_suggestion": suggestion d'image pour illustrer ce chapitre

Assure-toi que le total des pages estimées fait environ {pages} pages.
Réponds UNIQUEMENT avec le JSON. Format: [{{"chapter_number": 1, "title": "...", ...}}]"""
    else:
        prompt = f"""You are a professional author. Create a detailed outline for this book:

Title: {book['title']}
Subtitle: {book.get('subtitle', '')}
Description: {book['description']}
Category: {book['category']}
Target pages: {pages}

Create exactly {num_chapters} chapters. For each chapter provide:
- "chapter_number": chapter number
- "title": chapter title
- "summary": content summary (2-3 sentences)
- "key_points": list of 3-5 key points to cover
- "estimated_pages": estimated pages for this chapter
- "image_suggestion": image suggestion to illustrate this chapter

Make sure total estimated pages is around {pages}.
Respond ONLY with JSON. Format: [{{"chapter_number": 1, "title": "...", ...}}]"""

    try:
        response = await call_gemini(prompt, "You are a professional book author. Always respond with valid JSON only.")
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            cleaned = cleaned.rsplit("```", 1)[0]
        outline = json.loads(cleaned)
        
        await db.books.update_one(
            {"id": book_id},
            {"$set": {"outline": outline, "status": "outline_ready", "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"outline": outline}
    except json.JSONDecodeError:
        logger.error(f"Failed to parse outline JSON: {response[:200]}")
        raise HTTPException(status_code=500, detail="Failed to parse AI response for outline")
    except Exception as e:
        logger.error(f"Outline generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/books/{book_id}/outline")
async def update_outline(book_id: str, req: OutlineApproveRequest):
    await db.books.update_one(
        {"id": book_id},
        {"$set": {"outline": req.outline, "status": "outline_approved", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"status": "ok"}

@api_router.post("/books/{book_id}/generate-chapter/{chapter_num}")
async def generate_chapter(book_id: str, chapter_num: int):
    book = await db.books.find_one({"id": book_id}, {"_id": 0})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    outline = book.get("outline", [])
    chapter_outline = None
    for ch in outline:
        if ch.get("chapter_number") == chapter_num:
            chapter_outline = ch
            break
    
    if not chapter_outline:
        raise HTTPException(status_code=404, detail="Chapter not found in outline")
    
    lang = book.get("language", "fr")
    est_pages = chapter_outline.get("estimated_pages", 8)
    word_count = est_pages * 250
    
    if lang == "fr":
        prompt = f"""Tu es un auteur professionnel qui écrit le chapitre {chapter_num} du livre "{book['title']}".

Informations du chapitre:
- Titre: {chapter_outline['title']}
- Résumé: {chapter_outline['summary']}
- Points clés: {json.dumps(chapter_outline.get('key_points', []), ensure_ascii=False)}

Écris le contenu complet de ce chapitre. Le texte doit:
- Faire environ {word_count} mots ({est_pages} pages)
- Être professionnel, engageant et bien structuré
- Inclure des sous-sections avec des titres clairs (utilise ## pour les sous-titres)
- Couvrir tous les points clés mentionnés
- Inclure des exemples pratiques et des conseils concrets
- Être adapté pour un livre publié sur Amazon KDP

Écris UNIQUEMENT le contenu du chapitre, sans meta-commentaires."""
    else:
        prompt = f"""You are a professional author writing chapter {chapter_num} of the book "{book['title']}".

Chapter information:
- Title: {chapter_outline['title']}
- Summary: {chapter_outline['summary']}
- Key points: {json.dumps(chapter_outline.get('key_points', []))}

Write the complete content for this chapter. The text must:
- Be approximately {word_count} words ({est_pages} pages)
- Be professional, engaging and well-structured
- Include subsections with clear headings (use ## for subtitles)
- Cover all key points mentioned
- Include practical examples and concrete advice
- Be suitable for an Amazon KDP published book

Write ONLY the chapter content, no meta-commentary."""

    try:
        response = await call_gemini(prompt, f"You are writing a professional {book['category']} book. Write detailed, high-quality content.")
        
        chapter_data = {
            "chapter_number": chapter_num,
            "title": chapter_outline["title"],
            "content": response,
            "image_suggestion": chapter_outline.get("image_suggestion", ""),
            "image_url": None,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
        existing_chapters = book.get("chapters", [])
        existing_chapters = [c for c in existing_chapters if c.get("chapter_number") != chapter_num]
        existing_chapters.append(chapter_data)
        existing_chapters.sort(key=lambda x: x.get("chapter_number", 0))
        
        total_chapters = len(outline)
        generated_count = len(existing_chapters)
        new_status = "writing" if generated_count < total_chapters else "chapters_complete"
        
        await db.books.update_one(
            {"id": book_id},
            {"$set": {
                "chapters": existing_chapters,
                "status": new_status,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        return {
            "chapter": chapter_data,
            "progress": {"generated": generated_count, "total": total_chapters}
        }
    except Exception as e:
        logger.error(f"Chapter generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/books/{book_id}/generate-all-chapters")
async def generate_all_chapters_endpoint(book_id: str, background_tasks: BackgroundTasks):
    book = await db.books.find_one({"id": book_id}, {"_id": 0})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    await db.books.update_one(
        {"id": book_id},
        {"$set": {"status": "writing", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    background_tasks.add_task(generate_all_chapters_task, book_id)
    return {"status": "writing", "message": "Chapter generation started"}

async def generate_all_chapters_task(book_id: str):
    """Background task to generate all chapters one by one."""
    try:
        book = await db.books.find_one({"id": book_id}, {"_id": 0})
        if not book:
            return
        
        outline = book.get("outline", [])
        existing_chapters = book.get("chapters", [])
        generated_nums = {c.get("chapter_number") for c in existing_chapters}
        
        for ch in outline:
            ch_num = ch.get("chapter_number")
            if ch_num in generated_nums:
                continue
            
            try:
                lang = book.get("language", "fr")
                est_pages = ch.get("estimated_pages", 8)
                word_count = est_pages * 250
                
                if lang == "fr":
                    prompt = f"""Tu es un auteur professionnel qui écrit le chapitre {ch_num} du livre "{book['title']}".

Informations du chapitre:
- Titre: {ch['title']}
- Résumé: {ch['summary']}
- Points clés: {json.dumps(ch.get('key_points', []), ensure_ascii=False)}

Écris le contenu complet de ce chapitre ({word_count} mots environ, {est_pages} pages).
Le texte doit être professionnel, engageant, bien structuré avec des sous-sections (##).
Inclus des exemples pratiques et des conseils concrets.

Écris UNIQUEMENT le contenu du chapitre."""
                else:
                    prompt = f"""You are a professional author writing chapter {ch_num} of "{book['title']}".

Chapter info:
- Title: {ch['title']}
- Summary: {ch['summary']}
- Key points: {json.dumps(ch.get('key_points', []))}

Write the complete chapter content ({word_count} words, {est_pages} pages).
Be professional, engaging, well-structured with subsections (##).
Include practical examples and concrete advice.

Write ONLY the chapter content."""

                response = await call_gemini(prompt, f"You are writing a professional {book['category']} book.")
                
                chapter_data = {
                    "chapter_number": ch_num,
                    "title": ch["title"],
                    "content": response,
                    "image_suggestion": ch.get("image_suggestion", ""),
                    "image_url": None,
                    "generated_at": datetime.now(timezone.utc).isoformat()
                }
                
                await db.books.update_one(
                    {"id": book_id},
                    {"$push": {"chapters": chapter_data},
                     "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
                )
                
            except Exception as e:
                logger.error(f"Error generating chapter {ch_num}: {e}")
                await db.books.update_one(
                    {"id": book_id},
                    {"$set": {"status": "error", "error": f"Chapter {ch_num} failed: {str(e)}"}}
                )
                return
        
        await db.books.update_one(
            {"id": book_id},
            {"$set": {"status": "chapters_complete", "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    except Exception as e:
        logger.error(f"Background generation error: {e}")
        await db.books.update_one(
            {"id": book_id},
            {"$set": {"status": "error", "error": str(e)}}
        )

@api_router.post("/books/{book_id}/generate-image/{chapter_num}")
async def generate_chapter_image(book_id: str, chapter_num: int):
    book = await db.books.find_one({"id": book_id}, {"_id": 0})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    chapters = book.get("chapters", [])
    chapter = None
    for c in chapters:
        if c.get("chapter_number") == chapter_num:
            chapter = c
            break
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    settings = await get_settings()
    image_source = settings.get("image_source", "ai")
    suggestion = chapter.get("image_suggestion", chapter.get("title", ""))
    
    image_url = None
    if image_source in ("ai", "both"):
        try:
            prompt = f"Create a professional, high-quality illustration for a book chapter titled '{chapter['title']}'. The image should be: {suggestion}. Style: clean, professional, suitable for print publication. No text in the image."
            img_path, _ = await generate_image_ai(prompt, book_id, f"ch{chapter_num}")
            if img_path:
                image_url = f"/api/images/{book_id}_ch{chapter_num}.png"
        except Exception as e:
            logger.error(f"AI image generation failed: {e}")
    
    if not image_url and image_source in ("stock", "both"):
        stock_url = await fetch_stock_image(suggestion)
        if stock_url:
            image_url = stock_url
    
    if image_url:
        for i, c in enumerate(chapters):
            if c.get("chapter_number") == chapter_num:
                chapters[i]["image_url"] = image_url
                break
        
        await db.books.update_one(
            {"id": book_id},
            {"$set": {"chapters": chapters, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    
    return {"image_url": image_url}

@api_router.get("/images/{filename}")
async def serve_image(filename: str):
    file_path = IMAGES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(file_path), media_type="image/png")

@api_router.get("/books")
async def list_books():
    books = await db.books.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"books": books}

@api_router.get("/books/{book_id}")
async def get_book(book_id: str):
    book = await db.books.find_one({"id": book_id}, {"_id": 0})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@api_router.delete("/books/{book_id}")
async def delete_book(book_id: str):
    result = await db.books.delete_one({"id": book_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"status": "deleted"}

@api_router.get("/books/{book_id}/progress")
async def get_book_progress(book_id: str):
    book = await db.books.find_one({"id": book_id}, {"_id": 0, "chapters.content": 0})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    outline = book.get("outline", [])
    chapters = book.get("chapters", [])
    
    return {
        "status": book.get("status"),
        "total_chapters": len(outline),
        "generated_chapters": len(chapters),
        "chapter_titles": [{"number": c.get("chapter_number"), "title": c.get("title"), "has_image": bool(c.get("image_url"))} for c in chapters],
        "error": book.get("error")
    }

# ====== EXPORT ROUTES ======

@api_router.post("/books/{book_id}/export")
async def export_book(book_id: str, req: ExportRequest):
    book = await db.books.find_one({"id": book_id}, {"_id": 0})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if not book.get("chapters"):
        raise HTTPException(status_code=400, detail="Book has no chapters")
    
    fmt = req.format.lower()
    
    try:
        if fmt == "pdf":
            filepath = await export_pdf(book)
        elif fmt == "docx":
            filepath = await export_docx(book)
        elif fmt == "epub":
            filepath = await export_epub(book)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}")
        
        filename = f"{book['title'].replace(' ', '_')}_{book_id[:8]}.{fmt}"
        return FileResponse(
            str(filepath),
            media_type="application/octet-stream",
            filename=filename
        )
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def export_pdf(book):
    """Generate KDP-compliant PDF."""
    from reportlab.lib.pagesizes import A5
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image
    from reportlab.lib.units import inch, mm
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib import colors
    
    filepath = EXPORTS_DIR / f"{book['id']}.pdf"
    
    # KDP standard: 5.5 x 8.5 inches with margins
    page_w = 5.5 * inch
    page_h = 8.5 * inch
    
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=(page_w, page_h),
        leftMargin=0.75 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch
    )
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        'BookTitle', parent=styles['Title'],
        fontSize=24, spaceAfter=30, alignment=TA_CENTER
    ))
    styles.add(ParagraphStyle(
        'BookSubtitle', parent=styles['Normal'],
        fontSize=14, spaceAfter=20, alignment=TA_CENTER, textColor=colors.grey
    ))
    styles.add(ParagraphStyle(
        'ChapterTitle', parent=styles['Heading1'],
        fontSize=18, spaceBefore=20, spaceAfter=15
    ))
    styles.add(ParagraphStyle(
        'SubHeading', parent=styles['Heading2'],
        fontSize=13, spaceBefore=12, spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        'BookBody', parent=styles['Normal'],
        fontSize=11, leading=16, alignment=TA_JUSTIFY, spaceAfter=8
    ))
    
    story = []
    
    # Title page
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph(book['title'], styles['BookTitle']))
    if book.get('subtitle'):
        story.append(Paragraph(book['subtitle'], styles['BookSubtitle']))
    story.append(Spacer(1, 1 * inch))
    story.append(PageBreak())
    
    # Table of contents
    story.append(Paragraph("Table of Contents" if book.get('language') == 'en' else "Table des matières", styles['ChapterTitle']))
    story.append(Spacer(1, 20))
    for ch in book.get('outline', []):
        toc_text = f"Chapter {ch['chapter_number']}: {ch['title']}" if book.get('language') == 'en' else f"Chapitre {ch['chapter_number']} : {ch['title']}"
        story.append(Paragraph(toc_text, styles['BookBody']))
    story.append(PageBreak())
    
    # Chapters
    chapters = sorted(book.get('chapters', []), key=lambda x: x.get('chapter_number', 0))
    for chapter in chapters:
        ch_label = f"Chapter {chapter['chapter_number']}" if book.get('language') == 'en' else f"Chapitre {chapter['chapter_number']}"
        story.append(Paragraph(f"{ch_label}: {chapter['title']}", styles['ChapterTitle']))
        story.append(Spacer(1, 10))
        
        # Add chapter image if available
        if chapter.get('image_url') and chapter['image_url'].startswith('/api/images/'):
            img_filename = chapter['image_url'].replace('/api/images/', '')
            img_path = IMAGES_DIR / img_filename
            if img_path.exists():
                try:
                    img = Image(str(img_path), width=3.5 * inch, height=2.5 * inch)
                    story.append(img)
                    story.append(Spacer(1, 10))
                except Exception:
                    pass
        
        content = chapter.get('content', '')
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 6))
            elif line.startswith('## '):
                story.append(Paragraph(line[3:], styles['SubHeading']))
            elif line.startswith('# '):
                story.append(Paragraph(line[2:], styles['ChapterTitle']))
            else:
                # Escape XML special chars
                line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(line, styles['BookBody']))
        
        story.append(PageBreak())
    
    doc.build(story)
    return filepath

async def export_docx(book):
    """Generate KDP-compliant DOCX."""
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    
    filepath = EXPORTS_DIR / f"{book['id']}.docx"
    doc = Document()
    
    # Set page size to 5.5 x 8.5 inches (KDP standard)
    section = doc.sections[0]
    section.page_width = Inches(5.5)
    section.page_height = Inches(8.5)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.5)
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    
    # Title page
    for _ in range(6):
        doc.add_paragraph()
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_p.add_run(book['title'])
    run.font.size = Pt(28)
    run.bold = True
    
    if book.get('subtitle'):
        sub_p = doc.add_paragraph()
        sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = sub_p.add_run(book['subtitle'])
        run.font.size = Pt(14)
    
    doc.add_page_break()
    
    # TOC
    toc_title = "Table of Contents" if book.get('language') == 'en' else "Table des matières"
    doc.add_heading(toc_title, level=1)
    for ch in book.get('outline', []):
        label = f"Chapter {ch['chapter_number']}: {ch['title']}" if book.get('language') == 'en' else f"Chapitre {ch['chapter_number']} : {ch['title']}"
        doc.add_paragraph(label)
    doc.add_page_break()
    
    # Chapters
    chapters = sorted(book.get('chapters', []), key=lambda x: x.get('chapter_number', 0))
    for chapter in chapters:
        label = f"Chapter {chapter['chapter_number']}" if book.get('language') == 'en' else f"Chapitre {chapter['chapter_number']}"
        doc.add_heading(f"{label}: {chapter['title']}", level=1)
        
        content = chapter.get('content', '')
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            elif line.startswith('## '):
                doc.add_heading(line[3:], level=2)
            elif line.startswith('# '):
                doc.add_heading(line[2:], level=1)
            else:
                p = doc.add_paragraph(line)
                p.paragraph_format.space_after = Pt(6)
        
        doc.add_page_break()
    
    doc.save(str(filepath))
    return filepath

async def export_epub(book):
    """Generate EPUB."""
    from ebooklib import epub
    
    filepath = EXPORTS_DIR / f"{book['id']}.epub"
    
    ebook = epub.EpubBook()
    ebook.set_identifier(book['id'])
    ebook.set_title(book['title'])
    ebook.set_language(book.get('language', 'fr'))
    
    # CSS
    style = epub.EpubItem(
        uid="style", file_name="style/default.css", media_type="text/css",
        content=b"body { font-family: Georgia, serif; line-height: 1.8; } h1 { font-size: 1.5em; margin-top: 2em; } h2 { font-size: 1.2em; margin-top: 1.5em; } p { text-align: justify; margin-bottom: 0.5em; }"
    )
    ebook.add_item(style)
    
    chapters_epub = []
    chapters = sorted(book.get('chapters', []), key=lambda x: x.get('chapter_number', 0))
    
    for chapter in chapters:
        ch = epub.EpubHtml(
            title=chapter['title'],
            file_name=f"chapter_{chapter['chapter_number']}.xhtml",
            lang=book.get('language', 'fr')
        )
        
        content_html = f"<h1>{chapter['title']}</h1>"
        for line in chapter.get('content', '').split('\n'):
            line = line.strip()
            if not line:
                continue
            elif line.startswith('## '):
                content_html += f"<h2>{line[3:]}</h2>"
            elif line.startswith('# '):
                content_html += f"<h1>{line[2:]}</h1>"
            else:
                content_html += f"<p>{line}</p>"
        
        ch.content = content_html
        ch.add_item(style)
        ebook.add_item(ch)
        chapters_epub.append(ch)
    
    ebook.toc = [(epub.Section(ch.title), [ch]) for ch in chapters_epub]
    ebook.add_item(epub.EpubNcx())
    ebook.add_item(epub.EpubNav())
    ebook.spine = ['nav'] + chapters_epub
    
    epub.write_epub(str(filepath), ebook)
    return filepath

# ====== ROOT ======

@api_router.get("/")
async def root():
    return {"message": "Lumina Press API", "version": "1.0.0"}

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
