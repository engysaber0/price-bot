"""
Image search: user sends a photo → bot identifies product and searches stores.
Uses Google Vision API if configured, otherwise uses SerpAPI reverse image search.
"""
import io
import base64
import logging
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config.settings import settings
from scrapers.search_engine import multi_store_search
from utils.formatters import format_price_results

logger = logging.getLogger(__name__)


async def image_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo = update.message.photo[-1]  # highest resolution

    msg = await update.message.reply_text("📸 جاري تحليل الصورة...")

    # Download photo
    file = await context.bot.get_file(photo.file_id)
    img_bytes = await file.download_as_bytearray()

    product_name = None

    # Try Google Vision first
    if settings.GOOGLE_VISION_API_KEY:
        product_name = await _vision_detect(bytes(img_bytes))

    # Fallback: SerpAPI reverse image search
    if not product_name and settings.SERPAPI_KEY:
        product_name = await _serpapi_reverse_image(bytes(img_bytes))

    if not product_name:
        await msg.edit_text(
            "❌ لم أستطع التعرف على المنتج في الصورة.\n"
            "جرب إرسال صورة أوضح أو اكتب اسم المنتج مباشرة."
        )
        return

    await msg.edit_text(f"✅ تم التعرف على: *{product_name}*\n⏳ جاري البحث عن أفضل سعر...",
                        parse_mode="Markdown")

    results = await multi_store_search(product_name)

    if not results:
        await msg.edit_text(f"✅ تعرفت على: *{product_name}*\n❌ لكن لم أجد له أسعار حالياً.",
                            parse_mode="Markdown")
        return

    text = f"📸 *نتائج لـ: {product_name}*\n\n" + format_price_results(results)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu:main")
    ]])
    await msg.edit_text(text, parse_mode="Markdown", reply_markup=kb,
                        disable_web_page_preview=True)


async def _vision_detect(img_bytes: bytes) -> str | None:
    """Google Cloud Vision — label detection."""
    try:
        b64 = base64.b64encode(img_bytes).decode()
        payload = {
            "requests": [{
                "image": {"content": b64},
                "features": [
                    {"type": "LABEL_DETECTION", "maxResults": 5},
                    {"type": "PRODUCT_SEARCH"},
                    {"type": "WEB_DETECTION", "maxResults": 3},
                ]
            }]
        }
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"https://vision.googleapis.com/v1/images:annotate?key={settings.GOOGLE_VISION_API_KEY}",
                json=payload
            )
        data = r.json()
        resp = data.get("responses", [{}])[0]

        # Try web entities first (most accurate for products)
        web = resp.get("webDetection", {})
        entities = web.get("webEntities", [])
        if entities:
            return entities[0].get("description", "")

        # Fallback to labels
        labels = resp.get("labelAnnotations", [])
        if labels:
            return labels[0].get("description", "")
    except Exception as e:
        logger.error(f"Vision API error: {e}")
    return None


async def _serpapi_reverse_image(img_bytes: bytes) -> str | None:
    """Use SerpAPI Google Lens for reverse image search."""
    if not settings.SERPAPI_KEY:
        return None
    try:
        # Upload image to a temp service or use base64 endpoint
        # SerpAPI Google Lens requires a URL — upload to tmpfiles.org as fallback
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": ("image.jpg", img_bytes, "image/jpeg")}
            )
        url_data = resp.json()
        img_url = url_data.get("data", {}).get("url", "")
        if not img_url:
            return None
        # Convert to direct URL
        img_url = img_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")

        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://serpapi.com/search",
                params={
                    "engine": "google_lens",
                    "url": img_url,
                    "api_key": settings.SERPAPI_KEY,
                }
            )
        data = r.json()
        visual_matches = data.get("visual_matches", [])
        if visual_matches:
            return visual_matches[0].get("title", "")
    except Exception as e:
        logger.error(f"SerpAPI reverse image error: {e}")
    return None
