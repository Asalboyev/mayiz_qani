# SafeDrop AI — Texnik Hujjatlar

> **Loyiha maqsadi:** "Xavfsiz shahar" tizimidagi videokuzatuv kameralari zakladchiklarni avtomatik aniqlay olmaydi. SafeDrop AI ushbu muammoni sun'iy intellekt yordamida hal qiladi — kamera orqali shubhali harakatlarni real vaqtda aniqlaydi, shaxsni Face ID bilan solishtiradi va geolokatsiya bilan birga huquq-tartibot idoralariga xabar yuboradi.

---

## 📋 Mundarija

1. [Umumiy arxitektura](#1-umumiy-arxitektura)
2. [Texnologiyalar stacki](#2-texnologiyalar-stacki)
3. [Backend — FastAPI](#3-backend--fastapi)
4. [Frontend — React](#4-frontend--react)
5. [AI / ML tizimi](#5-ai--ml-tizimi)
6. [Multi-Camera Re-ID](#6-multi-camera-re-id)
7. [Telegram bot integratsiyasi](#7-telegram-bot-integratsiyasi)
8. [Face ID tizimi](#8-face-id-tizimi)
9. [Dataset manbalar](#9-dataset-manbalar)
10. [Kutubxonalar ro'yxati](#10-kutubxonalar-royxati)
11. [API endpointlar](#11-api-endpointlar)
12. [Loyihani ishga tushirish](#12-loyihani-ishga-tushirish)

---

## 1. Umumiy arxitektura

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                             │
│              React 18 + Vite  (port 5173 HTTPS)            │
│   Operator Dashboard │ Citizen Portal │ Phone Cam Page      │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST API + MJPEG Stream
┌──────────────────────────▼──────────────────────────────────┐
│                        BACKEND                              │
│              FastAPI + Uvicorn  (port 8001 HTTP)            │
│  /camera/stream  │  /alerts  │  /reid  │  /faceid  │  /auth │
└──────┬───────────┬───────────┬─────────────────────────────┘
       │           │           │
  ┌────▼───┐  ┌───▼────┐  ┌──▼──────────┐
  │OpenCV  │  │ YOLOv8 │  │ Reid Service│
  │Camera  │  │  Model │  │ (Re-ID)     │
  └────────┘  └───┬────┘  └─────────────┘
                  │
         ┌────────▼────────┐
         │  Behavior Engine │
         │  (Python logic)  │
         └────────┬────────┘
                  │
      ┌───────────▼──────────┐
      │   Telegram Bot API   │
      │  (Alert + Evidence)  │
      └──────────────────────┘
```

---

## 2. Texnologiyalar stacki

### Backend
| Texnologiya | Versiya | Maqsad |
|---|---|---|
| **Python** | 3.9+ | Asosiy backend tili |
| **FastAPI** | 0.100+ | REST API framework |
| **Uvicorn** | latest | ASGI server |
| **OpenCV (cv2)** | 4.8+ | Kamera oqimi, frame qayta ishlash |
| **Ultralytics YOLOv8** | 8.x | Object detection modeli |
| **NumPy** | 1.24+ | Rasm massivlari, Re-ID hisoblash |
| **python-dotenv** | latest | Environment variables |
| **requests** | latest | Telegram API so'rovlari |
| **Pillow** | latest | Rasm formatlari bilan ishlash |

### Frontend
| Texnologiya | Versiya | Maqsad |
|---|---|---|
| **React** | 18 | UI framework |
| **Vite** | 8.x | Build tool + dev server |
| **@vitejs/plugin-basic-ssl** | latest | HTTPS (telefon kamera uchun) |
| **CSS Variables** | — | Light/dark mode theming |
| **Fetch API** | native | Backend bilan aloqa |
| **getUserMedia API** | native | Telefon kamera stream |
| **Canvas API** | native | Frame capture va yuborish |

### Infratuzilma
| Texnologiya | Maqsad |
|---|---|
| **Telegram Bot API** | Alert yuborish (sendMessage, sendPhoto, sendLocation) |
| **MJPEG Streaming** | Real-time video stream brauzerga |
| **QR code API** | Telefon kamera ulash uchun QR |
| **JSON fayllar** | Ma'lumotlar bazasi (SQLsiz, lightweight) |

---

## 3. Backend — FastAPI

### Fayl tuzilmasi
```
backend/
├── app/
│   ├── main.py                  # FastAPI app, barcha endpointlar
│   ├── services/
│   │   ├── camera_ai.py         # Kamera stream + YOLO + behavior engine
│   │   ├── telegram_service.py  # Telegram bot xabar yuborish
│   │   ├── face_match_service.py# Yuz solishtirish logikasi
│   │   └── reid_service.py      # Multi-Camera Re-Identification
│   └── data/
│       ├── evidence/            # Alert rasmlari
│       ├── citizens/            # Fuqaro ma'lumotlari
│       └── faceid/              # Face ID baza rasmlari
├── .env                         # Secret keys (gitda yo'q)
└── requirements.txt
```

### `.env` konfiguratsiya
```env
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_CHAT_ID=<chat_id>

CAMERA_NAME=Guliston Test Kamerasi 01
CAMERA_LAT=40.4897
CAMERA_LON=68.7842
CAMERA_INDEX=0          # 0 = birinchi kamera
CAMERA_SOURCE=          # bo'sh = local webcam, RTSP URL bo'lsa shu

YOLO_MODEL=yolov8n.pt
YOLO_IMGSZ=960
YOLO_CONFIDENCE=0.22

STATIONARY_SECONDS_TO_ALERT=7   # 7 soniya bir joyda tursa
ALERT_COOLDOWN_SECONDS=10
PROCESS_EVERY_N_FRAMES=3        # Har 3 framedan birini analyze qilish
```

---

## 4. Frontend — React

### Sahifalar
```
frontend/src/
├── pages/
│   ├── Landing.jsx          # Bosh sahifa (citizen / operator tanlash)
│   ├── OperatorLogin.jsx    # Operator login
│   ├── OperatorDashboard.jsx# Asosiy operator panel
│   ├── CitizenPortal.jsx    # Fuqaro portal
│   └── PhoneCam.jsx         # Telefon kamera sahifasi (/phone-cam)
├── api.js                   # Backend bilan aloqa (fetch wrapper)
├── App.jsx                  # Router (state-based, no React Router)
└── App.css                  # Barcha stillar (light/dark mode)
```

### Operator panel tuzilmasi (tablar)
```
OperatorDashboard
├── 📡 AI Alerts tab
│   ├── Real-time alert ro'yxati
│   ├── Evidence gallery (photo burst)
│   ├── Face match natijasi
│   └── Status yangilash (tasdiqlash/rad etish)
│
├── 📷 Live Cameras tab
│   ├── Camera list (qo'shish/o'chirish)
│   ├── CAM-01: Mac kamera (backend MJPEG AI stream)
│   ├── CAM-02: Telefon kamera (getUserMedia + AI analyze loop)
│   ├── Device picker (QR kod bilan)
│   └── Multi-Camera Re-ID panel
│
├── 📋 Citizen Reports tab
│   ├── Fuqaro xabarlari ro'yxati
│   └── Status yangilash
│
├── 🆔 Face ID baza tab
│   ├── Shaxslar bazasi
│   └── Yangi shaxs qo'shish (rasm bilan)
│
├── 🔍 AI Face Matchmaking tab
│   ├── Oxirgi alert yuzini baza bilan solishtirish
│   └── Match foizi va natija
│
└── 📊 Audit Logs tab
    └── Barcha operator harakatlari
```

### Telefon kamera arxitekturasi
```
iPhone brauzer (https://LAN-IP:5173/phone-cam)
    ↓
getUserMedia({ facingMode: "environment" })  ← orqa kamera
    ↓
<canvas> → drawImage(video) → toBlob(jpeg)
    ↓  har 100ms
POST http://LAN-IP:8001/camera/analyze
    ↓
Backend: YOLO analyze → annotated JPEG
    ↓
createObjectURL(blob) → <img src=...>
```

---

## 5. AI / ML tizimi

### YOLOv8 detection
```python
# Aniqlash klasslari (COCO dataset)
PERSON_CLASS_ID = 0          # Odam
CELL_PHONE_CLASS_ID = 67     # Telefon

SUSPICIOUS_OBJECT_CLASS_IDS = {
    24,  # backpack
    26,  # handbag
    28,  # suitcase
    39,  # bottle
    67,  # cell phone
}
```

### Behavior Engine — shubhali harakat aniqlash logikasi

#### 1. Loitering (bir joyda turish)
```
Agar odam > 7 soniya bir joyda tursa → ALERT
Harakat masofasi > 42px bo'lsa → timer reset
```

#### 2. Photo pose (rasm olish pozasi)
```
Telefon person box ichida va old zonada bo'lsa → shubhali
Quloq zonasida bo'lsa → skip (call bo'lishi mumkin)
Threshold: 0.7 soniya
```

#### 3. Crouching (egilish/bukilish)
```
Person height / baseline_height < 0.78 → egilgan
Threshold: 0.8 soniya
```

#### 4. Object drop (narsa tashlash)
```
Object count ko'paydi + object pastki zonada + odam yaqinida → ALERT
Narsa yerga qo'yilganligi 0.5 soniyadan ko'p aniqlansa → ALERT
```

#### 5. Lower zone motion (pastki zona harakati)
```
Background subtraction → motion score
Person pastki 40% zonasida motion > threshold → shubhali
```

### Risk scoring
```python
# Risk foizi hisoblanishi
score = 0
if stationary:   score += 35
if photo_pose:   score += 30
if crouching:    score += 20
if drop:         score += 40
if lower_motion: score += 15

# Event types
"loitering"           → 7+ soniya bir joyda
"phone_photo"         → rasm olish pozasi
"crouch_or_bending"   → egilish
"drop_detected"       → narsa tashash
"suspicious_combined" → bir nechta signal bir vaqtda
```

### Evidence yig'ish
```
Alert paytida:
├── Pre-event buffer: oxirgi 1.5 soniya (120 frame buffer)
├── Live capture: 2.5 soniya davom etadi
├── Burst count: 6 ta rasm
├── Face crop: person box dan yuz qismi
├── Zoom crop: drop zone yoki person zoom
└── Best frame: eng yuqori confidence bilan
```

---

## 6. Multi-Camera Re-ID

### Printsip
Har bir aniqlangan odamdan **appearance feature vector** chiqariladi va barcha kameraalar bo'yicha kuzatiladi.

### Feature extraction
```python
# 1. HSV color histogram (6 ta horizontal stripe)
#    → Yoritish o'zgarishiga chidamli rang tavsifi
# 2. Gradient magnitude histogram (tekstura)
#    → Kiyim teksturasini aniqlash
# 3. L2 normalization
#    → Cosine similarity uchun

Feature vector: ~160-dim float32
```

### Matching
```python
REID_SIMILARITY_THRESHOLD = 0.72  # 72% mos kelsa = bir xil odam
REID_TRACK_TTL_SECONDS = 120      # 2 daqiqa ko'rinmasa — yangi odam
```

### Cross-camera detection
```
Odam A kamerada ko'rindi → track yaratildi (ID: abc123)
Odam B kamerada ko'rindi → feature match > 72% → CROSS-CAMERA alert
Operator panelda: Re-ID: abc123 ⚠ CROSS-CAMERA seen:3x (qizil)
```

---

## 7. Telegram bot integratsiyasi

### Yuboriluvchi ma'lumotlar
```
Alert paytida Telegram ga:
1. 📍 Geolokatsiya (kamera lat/lon)
2. 📸 Evidence rasm (annotatsiyalangan)
3. 📝 Xabar:
   ⚠️ SHUBHALI HARAKAT ANIQLANDI
   📍 Kamera: Guliston Test Kamerasi 01
   🎯 Ishonchlilik: 87.3%
   🕐 Vaqt: 2026-06-27 14:32:11
   📋 Sabablar:
   - 🔴 Shaxs 9 soniya bir joyda turdi
   - ⬇ Egilish aniqlandi
```

### Bot sozlamalari (`.env`)
```env
TELEGRAM_BOT_TOKEN=8835814216:AAG8lwT...
TELEGRAM_CHAT_ID=5008167286
```

---

## 8. Face ID tizimi

### Arxitektura
```
Ro'yxatdan o'tish paytida:
Fuqaro rasm yuklaydi → backend saqlaydi → Face ID bazaga qo'shiladi

Alert paytida:
Kamera → yuz crop → Face ID baza bilan solishtirish
→ Match foizi (0-100%)
→ Operator panelda natija ko'rsatiladi
```

### Saqlash
```
backend/app/data/
├── faceid/
│   ├── faceid_records.json    # Barcha shaxslar ro'yxati
│   └── faces/                 # Yuz rasmlari
│       ├── uuid1.jpg
│       └── uuid2.jpg
└── citizens/
    ├── citizens.json          # Fuqaro akkauntlari
    └── faces/                 # Fuqaro yuz rasmlari
```

### Face match API
```
GET  /face-match/latest          → Oxirgi alert uchun match
GET  /face-match/alerts/{id}     → Muayyan alert uchun match
GET  /faceid/records             → Baza ro'yxati
POST /faceid/records             → Yangi shaxs qo'shish
```

---

## 9. Dataset manbalar

### 🎯 Zakladchi aniqlash uchun (loyiha uchun asosiy)

| Dataset | Nima bor | Yuklab olish |
|---|---|---|
| **UCF-Crime** | 13 turdagi jinoyat: Theft, Robbery, Fighting | [GitHub](https://github.com/WaqasSultani/AnomalyDetectionCVPR2018) |
| **ShanghaiTech Campus** | Anomaly detection, loitering, shubhali harakat | Aloqa orqali |
| **Avenue Dataset (CUHK)** | Odatiy bo'lmagan harakat detection | CUHK university |
| **Roboflow — abandoned object** | Tashlab ketilgan narsalar | roboflow.com/universe |
| **Roboflow — loitering** | Bir joyda uzoq turish | roboflow.com/universe |

### 👤 Person Re-ID uchun

| Dataset | Identitylar | Kameralar | Yuklab olish |
|---|---|---|---|
| **Market-1501** | 1,501 odam | 6 kamera | Kaggle |
| **DukeMTMC-reID** | 1,812 odam | 8 kamera | GitHub |
| **CUHK03** | 1,467 odam | 2 kamera | CUHK |
| **MSMT17** | 4,101 odam | 15 kamera | arxiv |

### 🏛 Davlat tashkilotlaridan

| Muassasa | Nima so'rash | Qanday murojaat |
|---|---|---|
| **IIV — Raqamli texnologiyalar bo'limi** | Arxiv kamera yozuvlari (anonimlashtirilib) | Rasmiy ariza + NDA |
| **"Xavfsiz shahar" markazi (Toshkent)** | Pilot loyiha uchun kamera ulanishi | Hackathon natijasini taqdim etish |
| **Giyohvandlikka qarshi kurash** | Real zakladchi video misollari | Prokuratura orqali |

### 📸 O'z datasetingizni yaratish (TAVSIYA ETILADI)

```
1. Simulyatsiya yozuvlari:
   - Sumkadan narsa chiqarib qo'yish (50 video)
   - Burchakka egilib narsa yashirish (50 video)
   - Bir joyda 10-30 soniya turish (30 video)
   - Tez ketib qolish (30 video)
   - Narsa olib ketish (pickup) (30 video)

2. Label qilish:
   - labelstud.io (bepul, professional)
   - roboflow.com/annotate (YOLO formatga to'g'ridan eksport)

3. Fine-tuning:
   yolo train model=yolov8n.pt data=custom.yaml epochs=50
```

---

## 10. Kutubxonalar ro'yxati

### Backend (requirements.txt)
```txt
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
opencv-python>=4.8.0
ultralytics>=8.0.0        # YOLOv8
numpy>=1.24.0
pillow>=10.0.0
python-dotenv>=1.0.0
requests>=2.31.0
python-multipart>=0.0.6   # File upload uchun
```

### Frontend (package.json)
```json
{
  "dependencies": {
    "react": "^18.0.0",
    "react-dom": "^18.0.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.0.0",
    "@vitejs/plugin-basic-ssl": "^1.0.0",
    "vite": "^8.0.0"
  }
}
```

---

## 11. API endpointlar

### Kamera
```
GET  /camera/stream          → MJPEG live stream (AI annotatsiyalangan)
GET  /camera/status          → Kamera holati, detection natijalari
POST /camera/analyze         → Telefon frame → annotated JPEG qaytaradi
```

### Alertlar
```
GET  /alerts                 → Barcha alertlar
POST /alerts                 → Yangi alert yaratish
POST /alerts/demo            → Demo alert (test uchun)
PATCH /alerts/{id}/status    → Status yangilash (tasdiqlash/rad)
```

### Fuqaro portali
```
POST /citizens/register      → Ro'yxatdan o'tish
POST /citizens/login         → Login (telefon raqami bilan)
GET  /citizen/reports        → Barcha xabarlar
POST /citizen/reports        → Yangi xabar
POST /citizen/reports/upload → Evidence rasm bilan xabar
PATCH /citizen/reports/{id}/status → Status yangilash
```

### Face ID
```
GET  /faceid/records         → Baza ro'yxati
POST /faceid/records         → Yangi shaxs qo'shish
GET  /face-match/latest      → Oxirgi alert face match
GET  /face-match/alerts/{id} → Muayyan alert face match
```

### Multi-Camera Re-ID
```
GET    /reid/tracks          → Barcha aktiv tracklar
DELETE /reid/tracks          → Barcha tracklarni tozalash
```

### Tizim
```
GET  /health                 → Backend holati
GET  /network/info           → LAN IP, frontend/backend URL (QR uchun)
GET  /audit/logs             → Operator harakatlari logi
```

### Auth
```
POST /auth/operator-login    → Operator login
```

---

## 12. Loyihani ishga tushirish

### Talablar
```
- macOS / Linux / Windows
- Python 3.9+
- Node.js 20+ (yoki 22+)
- Webcam
```

### Backend ishga tushirish
```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# .env faylini to'ldiring
cp .env.example .env

# Serverini ishga tushirish
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend ishga tushirish
```bash
cd frontend
npm install
npm run dev -- --host
# https://localhost:5173 va https://LAN-IP:5173 da ishga tushadi
```

### Telefon kamera ulash
```
1. Mac va telefon bir xil Wi-Fi da bo'lsin
2. Mac brauzerda: Live Cameras → "Tashqi kamera" tugmasi
3. QR kod chiqadi (https://LAN-IP:5173/phone-cam)
4. Telefon bilan QR skan qiling
5. "Xavfsiz emas" ogohlantirish → Advanced → Proceed
6. "Kamerani yoqish" → Allow
7. AI analiz boshlanadi
```

---

## 📊 Tizim imkoniyatlari xulosasi

| Funksiya | Holati |
|---|---|
| ✅ Live camera stream (MJPEG) | Ishlamoqda |
| ✅ YOLOv8 person/phone/object detection | Ishlamoqda |
| ✅ Loitering (7 soniya) alert | Ishlamoqda |
| ✅ Crouching / bending detection | Ishlamoqda |
| ✅ Object drop detection | Ishlamoqda |
| ✅ Phone photo pose detection | Ishlamoqda |
| ✅ Smart zoom (drop zone / person) | Ishlamoqda |
| ✅ Photo evidence burst (6 rasm) | Ishlamoqda |
| ✅ Face crop + zoom crop saqlash | Ishlamoqda |
| ✅ Telegram alert (rasm + geolokatsiya) | Ishlamoqda |
| ✅ Operator login va panel | Ishlamoqda |
| ✅ Alert tasdiqlash / rad etish / izoh | Ishlamoqda |
| ✅ Fuqaro ro'yxat va login | Ishlamoqda |
| ✅ Evidence image upload | Ishlamoqda |
| ✅ Face ID baza | Ishlamoqda |
| ✅ AI Face Matchmaking | Ishlamoqda |
| ✅ Multi-Camera Re-ID | Ishlamoqda |
| ✅ Dual camera view (Mac + telefon) | Ishlamoqda |
| ✅ Light / Dark mode | Ishlamoqda |
| ✅ Responsive (mobil) | Ishlamoqda |
| ✅ Telefon kamera (QR + HTTPS) | Ishlamoqda |

---

*SafeDrop AI — Hackathon MVP · 2026*
