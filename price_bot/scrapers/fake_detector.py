"""
Fake/counterfeit product detector heuristics.
"""


FAKE_SIGNALS = [
    ("low_rating", lambda r: r.get("rating", 5) < 3.0),
    ("suspicious_price", lambda r: r.get("price", 999999) < 50),   # suspiciously cheap
    ("few_reviews", lambda r: 0 < r.get("reviews", 99) < 10),
    ("no_rating", lambda r: r.get("rating", 0) == 0),
]

SUSPICIOUS_KEYWORDS = [
    "replica", "copy", "fake", "clone", "imitation",
    "تقليد", "نسخة", "ماركة", "كوبي"
]


def analyze_product(product: dict) -> dict:
    """
    Returns:
      {
        "risk": "low" | "medium" | "high",
        "signals": [...warning strings],
        "score": 0-100  (higher = more suspicious)
      }
    """
    signals = []
    score = 0

    for name, check in FAKE_SIGNALS:
        if check(product):
            score += 25
            if name == "low_rating":
                signals.append(f"⚠️ تقييم منخفض جداً ({product.get('rating', 0):.1f}/5)")
            elif name == "suspicious_price":
                signals.append(f"⚠️ سعر مريب جداً ({product.get('price', 0):,.0f})")
            elif name == "few_reviews":
                signals.append(f"⚠️ عدد مراجعات قليل جداً ({product.get('reviews', 0)})")
            elif name == "no_rating":
                signals.append("⚠️ لا يوجد تقييم للمنتج")

    name_lower = product.get("name", "").lower()
    for kw in SUSPICIOUS_KEYWORDS:
        if kw in name_lower:
            score += 30
            signals.append(f"🚨 الاسم يحتوي على كلمة مريبة: '{kw}'")
            break

    if score == 0:
        risk = "low"
    elif score <= 25:
        risk = "medium"
    else:
        risk = "high"

    return {"risk": risk, "signals": signals, "score": min(score, 100)}


def format_fake_report(product: dict, analysis: dict) -> str:
    risk_emoji = {"low": "✅", "medium": "⚠️", "high": "🚨"}[analysis["risk"]]
    risk_text = {"low": "منخفضة", "medium": "متوسطة", "high": "عالية"}[analysis["risk"]]

    lines = [
        f"🔍 *تحليل المنتج: {product.get('name', 'غير محدد')}*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"{risk_emoji} *مستوى الخطر:* {risk_text} ({analysis['score']}%)",
        "",
    ]
    if analysis["signals"]:
        lines.append("*المؤشرات التحذيرية:*")
        lines.extend(analysis["signals"])
    else:
        lines.append("✅ لا توجد مؤشرات مشبوهة واضحة.")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "💡 *نصيحة:* تحقق دائماً من سياسة الإرجاع وتقييمات المشترين الموثقة.",
    ]
    return "\n".join(lines)
