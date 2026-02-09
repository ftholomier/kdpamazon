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
import re
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
- Utiliser ## pour les sous-titres de sections
- Utiliser **texte** pour le gras (mots importants, termes clés)
- Utiliser des listes à puces avec - pour les énumérations
- Couvrir tous les points clés mentionnés
- Inclure des exemples pratiques et des conseils concrets
- Ne PAS utiliser ### ou #### ou *** comme séparateurs
- Ne PAS commencer les paragraphes par des astérisques

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
        stock_url = await fetch_stock_image(suggestion, book_id, f"ch{chapter_num}")
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

@api_router.delete("/books/{book_id}/image/{chapter_num}")
async def delete_chapter_image(book_id: str, chapter_num: int):
    book = await db.books.find_one({"id": book_id}, {"_id": 0})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    chapters = book.get("chapters", [])
    for i, c in enumerate(chapters):
        if c.get("chapter_number") == chapter_num:
            old_url = c.get("image_url", "")
            chapters[i]["image_url"] = None
            # Delete local file if it exists
            if old_url and old_url.startswith("/api/images/"):
                img_filename = old_url.replace("/api/images/", "")
                img_path = IMAGES_DIR / img_filename
                if img_path.exists():
                    img_path.unlink()
            break
    
    await db.books.update_one(
        {"id": book_id},
        {"$set": {"chapters": chapters, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"status": "deleted"}

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
    book = await db.books.find_one({"id": book_id}, {"_id": 0})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Delete associated images
    for ch in book.get("chapters", []):
        img_url = ch.get("image_url", "")
        if img_url and img_url.startswith("/api/images/"):
            img_filename = img_url.replace("/api/images/", "")
            img_path = IMAGES_DIR / img_filename
            if img_path.exists():
                try:
                    img_path.unlink()
                except Exception:
                    pass
    
    # Delete export files
    for ext in ["pdf", "docx", "epub"]:
        export_path = EXPORTS_DIR / f"{book_id}.{ext}"
        if export_path.exists():
            try:
                export_path.unlink()
            except Exception:
                pass
    
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

# ====== MARKDOWN HELPERS ======

def parse_markdown_line(line):
    """Parse a markdown line and return (type, content, level)."""
    stripped = line.strip()
    if not stripped:
        return ("blank", "", 0)
    header_match = re.match(r'^(#{1,4})\s+(.+)$', stripped)
    if header_match:
        return ("heading", header_match.group(2).strip(), len(header_match.group(1)))
    list_match = re.match(r'^[-*]\s+(.+)$', stripped)
    if list_match:
        return ("list_item", list_match.group(1).strip(), 0)
    num_match = re.match(r'^\d+[.)]\s+(.+)$', stripped)
    if num_match:
        return ("num_list_item", num_match.group(1).strip(), 0)
    if re.match(r'^[-*_]{3,}$', stripped):
        return ("hr", "", 0)
    return ("paragraph", stripped, 0)

def md_to_xml(text):
    """Convert inline markdown to ReportLab XML (bold, italic)."""
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'\*{3}(.+?)\*{3}', r'<b><i>\1</i></b>', text)
    text = re.sub(r'_{3}(.+?)_{3}', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*{2}(.+?)\*{2}', r'<b>\1</b>', text)
    text = re.sub(r'_{2}(.+?)_{2}', r'<b>\1</b>', text)
    text = re.sub(r'(?<![*])\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'`(.+?)`', r'<font face="Courier" size="9">\1</font>', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'<u>\1</u>', text)
    return text

def md_to_html(text):
    """Convert inline markdown to HTML (bold, italic, links)."""
    import html as html_mod
    text = html_mod.escape(text)
    text = re.sub(r'\*{3}(.+?)\*{3}', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'_{3}(.+?)_{3}', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*{2}(.+?)\*{2}', r'<strong>\1</strong>', text)
    text = re.sub(r'_{2}(.+?)_{2}', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<![*])\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    return text

def md_clean(text):
    """Strip all markdown to plain text."""
    text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}(.+?)_{1,3}', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    return text

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
        
        filename = f"{book['title'].replace(' ', '_')}_{book['id'][:8]}.{fmt}"
        return FileResponse(
            str(filepath),
            media_type="application/octet-stream",
            filename=filename
        )
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def export_pdf(book):
    """Generate KDP-compliant PDF with page numbers and TOC."""
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak, 
        Image, Table, TableStyle, KeepTogether
    )
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
    from reportlab.lib import colors
    from reportlab.platypus.flowables import HRFlowable
    
    filepath = EXPORTS_DIR / f"{book['id']}.pdf"
    page_w = 5.5 * inch
    page_h = 8.5 * inch
    
    # Track page numbers per chapter
    chapter_pages = {}
    current_page = [0]
    
    def on_page(canvas, doc):
        current_page[0] = doc.page
        page_num = doc.page
        # Add page number at bottom center (skip title page)
        if page_num > 1:
            canvas.saveState()
            canvas.setFont("Helvetica", 9)
            canvas.setFillColor(colors.Color(0.4, 0.4, 0.4))
            canvas.drawCentredString(page_w / 2, 0.4 * inch, str(page_num))
            canvas.restoreState()
    
    def on_first_page(canvas, doc):
        current_page[0] = doc.page
    
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=(page_w, page_h),
        leftMargin=0.75 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle('BookTitle', parent=styles['Title'],
        fontName='Times-Bold', fontSize=26, spaceAfter=12, alignment=TA_CENTER, leading=32))
    styles.add(ParagraphStyle('BookSubtitle', parent=styles['Normal'],
        fontName='Times-Italic', fontSize=14, spaceAfter=20, alignment=TA_CENTER,
        textColor=colors.Color(0.4, 0.4, 0.4)))
    styles.add(ParagraphStyle('ChapterLabel', parent=styles['Normal'],
        fontName='Helvetica', fontSize=10, textColor=colors.Color(0.5, 0.5, 0.5),
        spaceBefore=0, spaceAfter=4, alignment=TA_LEFT,
        tracking=3))
    styles.add(ParagraphStyle('ChapterTitle', parent=styles['Heading1'],
        fontName='Times-Bold', fontSize=20, spaceBefore=0, spaceAfter=20, leading=26))
    styles.add(ParagraphStyle('H2', parent=styles['Heading2'],
        fontName='Times-Bold', fontSize=14, spaceBefore=16, spaceAfter=8, leading=18))
    styles.add(ParagraphStyle('H3', parent=styles['Heading3'],
        fontName='Times-BoldItalic', fontSize=12, spaceBefore=12, spaceAfter=6, leading=16))
    styles.add(ParagraphStyle('H4', parent=styles['Normal'],
        fontName='Times-Bold', fontSize=11, spaceBefore=10, spaceAfter=4, leading=15))
    styles.add(ParagraphStyle('Body', parent=styles['Normal'],
        fontName='Times-Roman', fontSize=11, leading=16, alignment=TA_JUSTIFY, spaceAfter=6))
    styles.add(ParagraphStyle('ListItem', parent=styles['Normal'],
        fontName='Times-Roman', fontSize=11, leading=16, alignment=TA_LEFT, 
        spaceAfter=3, leftIndent=20, bulletIndent=10))
    styles.add(ParagraphStyle('TOCEntry', parent=styles['Normal'],
        fontName='Times-Roman', fontSize=11, leading=18, spaceAfter=2))
    styles.add(ParagraphStyle('TOCTitle', parent=styles['Heading1'],
        fontName='Times-Bold', fontSize=18, spaceBefore=0, spaceAfter=30, alignment=TA_LEFT))
    
    is_fr = book.get('language') != 'en'
    story = []
    
    # ---- TITLE PAGE ----
    story.append(Spacer(1, 2.5 * inch))
    story.append(Paragraph(md_to_xml(book['title']), styles['BookTitle']))
    if book.get('subtitle'):
        story.append(Spacer(1, 8))
        story.append(Paragraph(md_to_xml(book['subtitle']), styles['BookSubtitle']))
    story.append(Spacer(1, 1 * inch))
    story.append(PageBreak())
    
    # ---- TOC PLACEHOLDER (will show chapter names, page nums added as text) ----
    # We'll build the TOC after we know page numbers, so we use a 2-pass approach
    # For simplicity, build story first without TOC, calculate pages, then rebuild with TOC
    
    # First pass: build chapters to estimate pages
    chapters = sorted(book.get('chapters', []), key=lambda x: x.get('chapter_number', 0))
    outline = book.get('outline', [])
    
    # Build chapter content
    chapter_stories = []
    for chapter in chapters:
        ch_story = []
        ch_num = chapter['chapter_number']
        ch_label = f"CHAPITRE {ch_num}" if is_fr else f"CHAPTER {ch_num}"
        
        ch_story.append(Spacer(1, 0.5 * inch))
        ch_story.append(Paragraph(ch_label, styles['ChapterLabel']))
        ch_story.append(Paragraph(md_to_xml(chapter['title']), styles['ChapterTitle']))
        
        # Chapter image
        if chapter.get('image_url') and chapter['image_url'].startswith('/api/images/'):
            img_filename = chapter['image_url'].replace('/api/images/', '')
            img_path = IMAGES_DIR / img_filename
            if img_path.exists():
                try:
                    img = Image(str(img_path), width=3.5 * inch, height=2.5 * inch)
                    ch_story.append(img)
                    ch_story.append(Spacer(1, 12))
                except Exception:
                    pass
        
        # Parse content with proper markdown
        content = chapter.get('content', '')
        in_list = False
        for line in content.split('\n'):
            line_type, line_content, level = parse_markdown_line(line)
            
            if line_type == "blank":
                if in_list:
                    in_list = False
                ch_story.append(Spacer(1, 4))
            elif line_type == "heading":
                in_list = False
                xml_content = md_to_xml(line_content)
                if level == 1:
                    ch_story.append(Paragraph(xml_content, styles['ChapterTitle']))
                elif level == 2:
                    ch_story.append(Paragraph(xml_content, styles['H2']))
                elif level == 3:
                    ch_story.append(Paragraph(xml_content, styles['H3']))
                else:
                    ch_story.append(Paragraph(xml_content, styles['H4']))
            elif line_type == "list_item":
                in_list = True
                xml_content = md_to_xml(line_content)
                ch_story.append(Paragraph(f"\u2022  {xml_content}", styles['ListItem']))
            elif line_type == "num_list_item":
                in_list = True
                xml_content = md_to_xml(line_content)
                ch_story.append(Paragraph(f"\u2013  {xml_content}", styles['ListItem']))
            elif line_type == "hr":
                in_list = False
                ch_story.append(Spacer(1, 6))
                ch_story.append(HRFlowable(width="60%", thickness=0.5, color=colors.Color(0.7, 0.7, 0.7)))
                ch_story.append(Spacer(1, 6))
            elif line_type == "paragraph":
                in_list = False
                xml_content = md_to_xml(line_content)
                ch_story.append(Paragraph(xml_content, styles['Body']))
        
        ch_story.append(PageBreak())
        chapter_stories.append((ch_num, chapter['title'], ch_story))
    
    # Build a temporary doc to get page numbers
    # Simple approach: estimate TOC takes 1-2 pages, then count
    toc_page_start = 2  # After title page
    
    # Build TOC
    toc_label = "Table des matieres" if is_fr else "Table of Contents"
    story.append(Paragraph(toc_label, styles['TOCTitle']))
    
    # We estimate page numbers (TOC ~1 page, then chapters)
    estimated_page = toc_page_start + 2  # TOC takes ~1-2 pages
    for ch_num, ch_title, ch_story_items in chapter_stories:
        # Rough estimate: ~40 flowables per page
        ch_pages = max(1, len(ch_story_items) // 35)
        ch_label = f"Chapitre {ch_num}" if is_fr else f"Chapter {ch_num}"
        toc_text = f"{ch_label} : {md_to_xml(ch_title)}"
        dots = "." * 3
        toc_entry = f'{toc_text} {dots} <b>{estimated_page}</b>'
        story.append(Paragraph(toc_entry, styles['TOCEntry']))
        estimated_page += ch_pages
    
    story.append(PageBreak())
    
    # Add all chapters
    for ch_num, ch_title, ch_story_items in chapter_stories:
        story.extend(ch_story_items)
    
    doc.build(story, onFirstPage=on_first_page, onLaterPages=on_page)
    return filepath

async def export_docx(book):
    """Generate KDP-compliant DOCX with proper formatting."""
    from docx import Document
    from docx.shared import Inches, Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.style import WD_STYLE_TYPE
    
    filepath = EXPORTS_DIR / f"{book['id']}.docx"
    doc = Document()
    is_fr = book.get('language') != 'en'
    
    # Page setup - KDP standard
    section = doc.sections[0]
    section.page_width = Inches(5.5)
    section.page_height = Inches(8.5)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.5)
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    
    # Add page numbers
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    
    footer = section.footer
    footer.is_linked_to_previous = False
    footer_para = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Add page number field
    run = footer_para.add_run()
    fld_char1 = OxmlElement('w:fldChar')
    fld_char1.set(qn('w:fldCharType'), 'begin')
    run._r.append(fld_char1)
    
    run2 = footer_para.add_run()
    instr = OxmlElement('w:instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = ' PAGE '
    run2._r.append(instr)
    
    run3 = footer_para.add_run()
    fld_char2 = OxmlElement('w:fldChar')
    fld_char2.set(qn('w:fldCharType'), 'end')
    run3._r.append(fld_char2)
    
    # ---- TITLE PAGE ----
    for _ in range(8):
        doc.add_paragraph()
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_p.add_run(md_clean(book['title']))
    run.font.size = Pt(28)
    run.bold = True
    run.font.name = 'Georgia'
    
    if book.get('subtitle'):
        sub_p = doc.add_paragraph()
        sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = sub_p.add_run(md_clean(book['subtitle']))
        run.font.size = Pt(14)
        run.font.color.rgb = RGBColor(100, 100, 100)
        run.font.name = 'Georgia'
    
    doc.add_page_break()
    
    # ---- TOC ----
    toc_title = "Table des matieres" if is_fr else "Table of Contents"
    h = doc.add_heading(toc_title, level=1)
    for run in h.runs:
        run.font.name = 'Georgia'
    
    for ch in book.get('outline', []):
        ch_label = f"Chapitre {ch['chapter_number']}" if is_fr else f"Chapter {ch['chapter_number']}"
        p = doc.add_paragraph()
        run = p.add_run(f"{ch_label} : {md_clean(ch['title'])}")
        run.font.name = 'Georgia'
        run.font.size = Pt(11)
    
    doc.add_page_break()
    
    # ---- CHAPTERS ----
    chapters = sorted(book.get('chapters', []), key=lambda x: x.get('chapter_number', 0))
    for chapter in chapters:
        ch_num = chapter['chapter_number']
        ch_label = f"Chapitre {ch_num}" if is_fr else f"Chapter {ch_num}"
        
        # Chapter label (small)
        label_p = doc.add_paragraph()
        label_run = label_p.add_run(ch_label.upper())
        label_run.font.size = Pt(9)
        label_run.font.color.rgb = RGBColor(128, 128, 128)
        label_run.font.name = 'Arial'
        
        # Chapter title
        h = doc.add_heading(md_clean(chapter['title']), level=1)
        for run in h.runs:
            run.font.name = 'Georgia'
        
        # Chapter image
        if chapter.get('image_url') and chapter['image_url'].startswith('/api/images/'):
            img_filename = chapter['image_url'].replace('/api/images/', '')
            img_path = IMAGES_DIR / img_filename
            if img_path.exists():
                try:
                    doc.add_picture(str(img_path), width=Inches(3.5))
                    last_para = doc.paragraphs[-1]
                    last_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                except Exception:
                    pass
        
        # Parse content
        content = chapter.get('content', '')
        for line in content.split('\n'):
            line_type, line_content, level = parse_markdown_line(line)
            cleaned = md_clean(line_content)
            
            if line_type == "blank":
                continue
            elif line_type == "heading":
                doc_level = min(level + 1, 4)  # h1 in content -> heading 2 in doc
                h = doc.add_heading(cleaned, level=doc_level)
                for run in h.runs:
                    run.font.name = 'Georgia'
            elif line_type in ("list_item", "num_list_item"):
                p = doc.add_paragraph(style='List Bullet' if line_type == "list_item" else 'List Number')
                _add_formatted_runs(p, line_content)
                p.paragraph_format.space_after = Pt(3)
            elif line_type == "hr":
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run("_" * 30)
                run.font.color.rgb = RGBColor(180, 180, 180)
            elif line_type == "paragraph":
                p = doc.add_paragraph()
                _add_formatted_runs(p, line_content)
                p.paragraph_format.space_after = Pt(6)
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        
        doc.add_page_break()
    
    doc.save(str(filepath))
    return filepath

def _add_formatted_runs(paragraph, text):
    """Add runs with bold/italic formatting from markdown to a DOCX paragraph."""
    from docx.shared import Pt
    
    # Process bold+italic, bold, italic patterns
    parts = re.split(r'(\*{2,3}.+?\*{2,3}|_{2,3}.+?_{2,3})', text)
    for part in parts:
        if re.match(r'^\*{3}(.+?)\*{3}$', part) or re.match(r'^_{3}(.+?)_{3}$', part):
            clean = re.sub(r'^[*_]{3}|[*_]{3}$', '', part)
            run = paragraph.add_run(clean)
            run.bold = True
            run.italic = True
            run.font.name = 'Georgia'
            run.font.size = Pt(11)
        elif re.match(r'^\*{2}(.+?)\*{2}$', part) or re.match(r'^_{2}(.+?)_{2}$', part):
            clean = re.sub(r'^[*_]{2}|[*_]{2}$', '', part)
            run = paragraph.add_run(clean)
            run.bold = True
            run.font.name = 'Georgia'
            run.font.size = Pt(11)
        else:
            # Could still contain single * italic
            sub_parts = re.split(r'(\*[^*]+?\*)', part)
            for sp in sub_parts:
                if re.match(r'^\*([^*]+?)\*$', sp):
                    clean = sp.strip('*')
                    run = paragraph.add_run(clean)
                    run.italic = True
                    run.font.name = 'Georgia'
                    run.font.size = Pt(11)
                else:
                    # Strip remaining markdown
                    cleaned = md_clean(sp)
                    if cleaned:
                        run = paragraph.add_run(cleaned)
                        run.font.name = 'Georgia'
                        run.font.size = Pt(11)

async def export_epub(book):
    """Generate EPUB with proper formatting."""
    from ebooklib import epub
    
    filepath = EXPORTS_DIR / f"{book['id']}.epub"
    is_fr = book.get('language') != 'en'
    
    ebook = epub.EpubBook()
    ebook.set_identifier(book['id'])
    ebook.set_title(book['title'])
    ebook.set_language(book.get('language', 'fr'))
    
    # CSS
    css_content = """
    body { font-family: Georgia, 'Times New Roman', serif; line-height: 1.8; color: #1a1a1a; margin: 1em; }
    h1 { font-size: 1.6em; margin-top: 2em; margin-bottom: 0.5em; font-weight: bold; }
    h2 { font-size: 1.3em; margin-top: 1.5em; margin-bottom: 0.4em; font-weight: bold; }
    h3 { font-size: 1.1em; margin-top: 1.2em; margin-bottom: 0.3em; font-weight: bold; font-style: italic; }
    h4 { font-size: 1em; margin-top: 1em; font-weight: bold; }
    p { text-align: justify; margin-bottom: 0.5em; font-size: 1em; }
    ul, ol { margin-left: 1.5em; margin-bottom: 0.5em; }
    li { margin-bottom: 0.2em; }
    .chapter-label { font-size: 0.8em; color: #888; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 0; }
    .chapter-title { font-size: 1.8em; margin-top: 0.2em; }
    hr { border: none; border-top: 1px solid #ccc; margin: 1.5em 20%; }
    strong { font-weight: bold; }
    em { font-style: italic; }
    code { font-family: 'Courier New', monospace; font-size: 0.9em; background: #f5f5f5; padding: 0.1em 0.3em; }
    """
    style = epub.EpubItem(uid="style", file_name="style/default.css", 
                          media_type="text/css", content=css_content.encode('utf-8'))
    ebook.add_item(style)
    
    chapters_epub = []
    chapters = sorted(book.get('chapters', []), key=lambda x: x.get('chapter_number', 0))
    
    # TOC page
    toc_ch = epub.EpubHtml(title="Table des matieres" if is_fr else "Table of Contents",
                           file_name="toc.xhtml", lang=book.get('language', 'fr'))
    toc_label = "Table des matieres" if is_fr else "Table of Contents"
    toc_html = f"<h1>{toc_label}</h1>"
    for ch_data in chapters:
        ch_lbl = f"Chapitre {ch_data['chapter_number']}" if is_fr else f"Chapter {ch_data['chapter_number']}"
        toc_html += f'<p><a href="chapter_{ch_data["chapter_number"]}.xhtml">{ch_lbl} : {md_to_html(ch_data["title"])}</a></p>'
    toc_ch.content = toc_html
    toc_ch.add_item(style)
    ebook.add_item(toc_ch)
    
    for chapter in chapters:
        ch = epub.EpubHtml(
            title=chapter['title'],
            file_name=f"chapter_{chapter['chapter_number']}.xhtml",
            lang=book.get('language', 'fr')
        )
        
        ch_label = f"Chapitre {chapter['chapter_number']}" if is_fr else f"Chapter {chapter['chapter_number']}"
        content_html = f'<p class="chapter-label">{ch_label}</p>'
        content_html += f'<h1 class="chapter-title">{md_to_html(chapter["title"])}</h1>'
        
        in_list = False
        list_type = None
        content = chapter.get('content', '')
        
        for line in content.split('\n'):
            line_type, line_content, level = parse_markdown_line(line)
            
            if line_type in ("list_item", "num_list_item"):
                new_list_type = "ul" if line_type == "list_item" else "ol"
                if not in_list or list_type != new_list_type:
                    if in_list:
                        content_html += f"</{list_type}>"
                    content_html += f"<{new_list_type}>"
                    in_list = True
                    list_type = new_list_type
                content_html += f"<li>{md_to_html(line_content)}</li>"
                continue
            
            if in_list:
                content_html += f"</{list_type}>"
                in_list = False
                list_type = None
            
            if line_type == "blank":
                continue
            elif line_type == "heading":
                tag = f"h{min(level + 1, 4)}"
                content_html += f"<{tag}>{md_to_html(line_content)}</{tag}>"
            elif line_type == "hr":
                content_html += "<hr/>"
            elif line_type == "paragraph":
                content_html += f"<p>{md_to_html(line_content)}</p>"
        
        if in_list:
            content_html += f"</{list_type}>"
        
        ch.content = content_html
        ch.add_item(style)
        ebook.add_item(ch)
        chapters_epub.append(ch)
    
    ebook.toc = [toc_ch] + [(epub.Section(ch.title), [ch]) for ch in chapters_epub]
    ebook.add_item(epub.EpubNcx())
    ebook.add_item(epub.EpubNav())
    ebook.spine = ['nav', toc_ch] + chapters_epub
    
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
