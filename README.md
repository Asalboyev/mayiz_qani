# SafeDrop AI — Shubhali Harakatlarni Aniqlash Tizimi

Shahar kameralaridan real-vaqtda shubhali xatti-harakatlarni aniqlash va operator + fuqarolarni xabardor qilish uchun MVP platforma.

---

## Arxitektura

```
Browser (React + Vite)
        ↕ HTTP / MJPEG stream
FastAPI Backend (Python)
        ↕
OpenCV + YOLOv8 (kamera AI)
        ↕
Telegram Bot API
```

---

## Texnologiyalar

| Qatlam | Stack |
|---|---|
| Frontend | React 18, Vite, CSS |
| Backend | Python 3.9, FastAPI, Uvicorn |
| AI / CV | OpenCV, YOLOv8n (Ultralytics) |
| Xabarlar | Telegram Bot API |
| Video | MJPEG stream (HTTP multipart) |

---

## Loyiha tuzilmasi

```
mayiz_qani/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, barcha endpoint'lar
│   │   └── services/
│   │       ├── camera_ai.py         # OpenCV + YOLOv8 kamera moduli
│   │       └── telegram_service.py  # Telegram bot xabar yuborish
│   ├── .env                         # Sozlamalar (token, chat_id, kamera)
│   ├── requirements.txt
│   └── yolov8n.pt                   # YOLOv8 nano model
└── frontend/
    └── src/
        ├── api.js                   # Backend bilan barcha HTTP so'rovlar
        ├── App.jsx                  # Router
        └── pages/
            ├── Landing.jsx          # Bosh sahifa
            ├── OperatorLogin.jsx    # Operator kirish
            ├── OperatorDashboard.jsx# Alert boshqaruv paneli + live kamera
            └── CitizenPortal.jsx    # Fuqaro xabar portali
```

---

## Ishga tushirish

### Talablar
- Python 3.9+
- Node.js 20+

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

API docs: http://localhost:8001/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: http://localhost:5173

---

## `.env` sozlamalari

```env
TELEGRAM_BOT_TOKEN=<bot token>
TELEGRAM_CHAT_ID=<chat id>

CAMERA_NAME=Guliston Test Kamerasi 01
CAMERA_LAT=40.4897
CAMERA_LON=68.7842

CAMERA_INDEX=0              # Mac webcam = 0
YOLO_MODEL=yolov8n.pt
ALERT_ENDPOINT=http://127.0.0.1:8001/alerts
STATIONARY_SECONDS_TO_ALERT=7
ALERT_COOLDOWN_SECONDS=25
PROCESS_EVERY_N_FRAMES=3
```

---

## API endpoint'lar

### Kamera

| Method | Endpoint | Tavsif |
|---|---|---|
| GET | `/camera/status` | Kamera holati (ochiq/yopiq, odam bor/yo'q) |
| GET | `/camera/stream` | MJPEG live video stream |

### Alert (AI kamera)

| Method | Endpoint | Tavsif |
|---|---|---|
| GET | `/alerts` | Barcha alert'larni olish |
| POST | `/alerts` | Yangi alert yaratish |
| POST | `/alerts/demo` | Demo alert (test uchun) |
| PATCH | `/alerts/{id}/status` | Alertni tasdiqlash yoki rad etish |

### Fuqaro portali

| Method | Endpoint | Tavsif |
|---|---|---|
| POST | `/citizen/reports` | Fuqaro xabar yuboradi |
| GET | `/citizen/reports` | Barcha fuqaro xabarlarini olish |
| PATCH | `/citizen/reports/{id}/status` | Xabarni ko'rib chiqish |

### Boshqalar

| Method | Endpoint | Tavsif |
|---|---|---|
| GET | `/health` | Server holati |
| POST | `/auth/operator-login` | Operator kirishi |
| GET | `/audit/logs` | Audit loglari |
| GET | `/faceid/demo` | Demo FaceID profillari |

---

## Ma'lumotlar oqimi

```
1. OpenCV webcam'dan kadr oladi (30 fps)
2. Har 3-kadrda YOLOv8 odamni aniqlaydi (class_id=0)
3. Odam 7 soniya harakat qilmasa → shubhali deb belgilanadi
4. POST /alerts → Telegram'ga xabar + GPS lokatsiya yuboriladi
5. Operator dashboard'da alert ko'rinadi
6. Operator "Tasdiqlash" bosadi → Telegram'ga yana xabar
```

---

## Kamera AI qanday ishlaydi

```python
# 1. Odam aniqlash — YOLOv8
result = model(frame, imgsz=640, conf=0.45)
# class_id = 0 → "person" (COCO dataset)

# 2. Harakatsizlikni hisoblash
if move_distance < 40:          # piksel
    stationary_seconds += dt

# 3. Shubhali bo'lsa alert
if stationary_seconds >= 7:
    post_alert(confidence)
```

---

## Operator login

```
Username: admin      Password: safedrop123
Username: operator   Password: operator123
```

---

## Demo alert test

```bash
curl -X POST http://localhost:8001/alerts/demo
```

Telegram'da xabar + lokatsiya keladi.

---

## GitHub

https://github.com/Asalboyev/mayiz_qani
