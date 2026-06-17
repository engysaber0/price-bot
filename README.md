# 🤖 Price Comparison Telegram Bot

بوت تيليجرام ذكي لمقارنة الأسعار بين المتاجر الإلكترونية.

---

## 🚀 الميزات

| القسم | الوصف |
|-------|-------|
| 🔍 مقارنة الأسعار | بحث في نون، أمازون، علي إكسبريس وعرض أفضل سعر |
| ⚠️ كشف التقليد | تحليل المنتج وتحذير من التقليد والمنتجات المشبوهة |
| ⚔️ مقارنة منتجين | مقارنة كاملة بين منتجَين (iPhone vs Samsung مثلاً) |
| 📸 بحث بالصورة | إرسال صورة والبوت يبحث عن المنتج |
| 🎟 كوبونات الخصم | عرض أكواد الخصم لكل متجر |
| 🤖 وكيل الشراء | يحلل احتياجك ويختار أفضل منتج بميزانيتك |
| 🔔 تنبيهات الأسعار | إشعار عند انخفاض سعر منتج |
| 🎁 نظام الإحالات | ادعُ أصدقاء واكسب نقاطاً |
| 💳 اشتراكات | 3 خطط: مجانية / أساسية / احترافية |

---

## ⚙️ التثبيت

```bash
# 1. استنسخ المشروع
git clone <repo-url>
cd price_bot

# 2. أنشئ بيئة Python افتراضية
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# 3. ثبّت المتطلبات
pip install -r requirements.txt

# 4. اضبط المتغيرات
cp .env.example .env
# افتح .env وأضف BOT_TOKEN على الأقل

# 5. شغّل البوت
python main.py
```

---

## 🔑 المتغيرات المطلوبة

| المتغير | الوصف | مطلوب |
|---------|-------|-------|
| `BOT_TOKEN` | توكن البوت من @BotFather | ✅ |
| `SERPAPI_KEY` | مفتاح SerpAPI لجلب نتائج التسوق | موصى به |
| `NOON_AFFILIATE_ID` | معرف الأفلييت على نون | اختياري |
| `AMAZON_AFFILIATE_TAG` | تاج الأفلييت على أمازون | اختياري |
| `ALIEXPRESS_AFFILIATE_KEY` | مفتاح أفلييت علي إكسبريس | اختياري |
| `GOOGLE_VISION_API_KEY` | Google Vision للبحث بالصورة | اختياري |
| `STRIPE_SECRET_KEY` | Stripe للدفع الإلكتروني | اختياري |

---

## 🗂 هيكل المشروع

```
price_bot/
├── main.py                  # نقطة البداية
├── requirements.txt
├── .env.example
├── config/
│   └── settings.py          # إعدادات من .env
├── handlers/                # معالجات أوامر البوت
│   ├── start.py             # /start + القائمة الرئيسية
│   ├── menu.py              # توجيه أزرار الإنلاين
│   ├── search.py            # البحث الرئيسي + الوكيل الذكي
│   ├── compare.py           # مقارنة منتجين
│   ├── fake_detector.py     # كشف التقليد
│   ├── image_search.py      # البحث بالصورة
│   ├── coupons.py           # كوبونات الخصم
│   ├── smart_agent.py       # وكيل الشراء
│   ├── alerts.py            # تنبيهات الأسعار
│   ├── referral.py          # نظام الإحالات
│   └── subscription.py      # الاشتراكات
├── scrapers/
│   ├── search_engine.py     # محرك البحث (SerpAPI + Scrapers)
│   └── fake_detector.py     # منطق كشف التقليد
└── utils/
    ├── database.py          # SQLite async
    ├── affiliate.py         # بناء روابط الأفلييت
    └── formatters.py        # تنسيق رسائل التيليجرام
```

---

## 📦 قواعد البيانات

يستخدم البوت SQLite تلقائياً. للإنتاج، غيّر `DATABASE_URL` إلى PostgreSQL.

**الجداول:**
- `users` — المستخدمون، الخطط، النقاط، حالة المحادثة
- `price_alerts` — تنبيهات الأسعار النشطة
- `search_history` — سجل عمليات البحث
- `referral_rewards` — مكافآت الإحالة

---

## 💡 كيف تضيف متجراً جديداً؟

1. أضف دالة `search_<store>(query)` في `scrapers/search_engine.py`
2. أضفها في `multi_store_search()`
3. أضف بناء رابط الأفلييت في `utils/affiliate.py`

---

## 🔧 نشر على السيرفر (Ubuntu)

```bash
# تثبيت supervisor
sudo apt install supervisor

# إنشاء ملف الإعداد
sudo nano /etc/supervisor/conf.d/pricebot.conf
```

```ini
[program:pricebot]
command=/home/ubuntu/price_bot/venv/bin/python /home/ubuntu/price_bot/main.py
directory=/home/ubuntu/price_bot
autostart=true
autorestart=true
stderr_logfile=/var/log/pricebot.err.log
stdout_logfile=/var/log/pricebot.out.log
```

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start pricebot
```
