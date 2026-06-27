# Mayiz Qani 

Mayiz Qani — hackathon uchun tayyorlangan AI monitoring MVP platforma. Tizim kamera orqali shubhali harakatlarni aniqlaydi, operator panelida alert ko‘rsatadi, Telegram bot orqali xabar yuboradi va Face ID bazadagi rasmlar bilan yuz o‘xshashligini tekshiradi.

Loyiha real davlat FaceID tizimiga ulanmagan. Barcha Face ID va AI matching funksiyalari local demo baza asosida ishlaydi.

---

## Qisqacha maqsad

Loyiha “Xavfsiz shahar” konsepti uchun demo sifatida ishlab chiqilgan. Asosiy g‘oya: kamera shubhali harakatlarni kuzatadi, masalan:

- shaxs bir joyda uzoqroq turib qolishi;
- shaxs egilishi yoki bukilishi;
- pastki zona atrofida obyekt qo‘yish / olishga o‘xshash harakat;
- telefon bilan rasmga olishga o‘xshash holat;
- shubhali holat paytida yuz crop, zoom crop va bir nechta photo evidence saqlash.

Alert yakuniy hukm emas. Har bir holat operator tomonidan tekshiriladi.

---

## Nima qilingan

- Live camera stream.
- AI orqali person / phone / object detection.
- Shubhali harakat alertlari.
- Egilish / bukilish / pastki zona harakati monitoringi.
- 5 soniya bir joyda turib qolish holatini shubhali deb belgilash.
- Oddiy yurib o‘tishni alert qilmaslik uchun movement filter.
- Alert paytida bir nechta photo evidence saqlash.
- Face crop va zoom crop saqlash.
- Telegram bot orqali alert yuborish.
- Operator login.
- Operator paneli.
- Alertlarni tasdiqlash / rad etish / izoh yozish.
- Fuqarolar uchun ro‘yxatdan o‘tish va login.
- Fuqarolardan xabar yuborish.
- Fuqaro evidence image upload.
- Face ID baza.
- Ro‘yxatdan o‘tgan userlarning Face ID rasmini saqlash.
- Operator tomonidan Face ID bazaga odam qo‘shish.
- AI Face Matchmaking tab.
- Camera’dan olingan yuzni Face ID baza bilan solishtirish.
- Light mode / dark mode.
- Responsive frontend.

---

## Texnologiyalar va modullar nima qiladi

### Backend

#### Python

Python backendning asosiy dasturlash tili sifatida ishlatiladi. Kamera oqimini o‘qish, AI modelni ishga tushirish, rasm/crop fayllarini saqlash, Telegram botga so‘rov yuborish va Face ID matching logiclari Python orqali bajariladi.

#### FastAPI

FastAPI backend API server sifatida ishlaydi. Frontend barcha ma’lumotlarni FastAPI endpointlari orqali oladi yoki yuboradi.

FastAPI orqali quyidagilar bajariladi:

- operator login;
- alertlarni olish;
- alert statusini yangilash;
- citizen register/login;
- citizen report yuborish;
- Face ID bazani olish va unga odam qo‘shish;
- Face Matchmaking natijasini olish;
- camera streamni frontendga berish.

Asosiy fayl:

```text
backend/app/main.py
```

#### OpenCV

OpenCV camera stream bilan ishlash uchun ishlatiladi.

OpenCV vazifalari:

- laptop camera yoki RTSP IP camera’dan frame olish;
- frame’larni MJPEG streamga aylantirish;
- person, face, zoom crop rasmlarini saqlash;
- evidence image ustiga text/label/box chizish;
- pastki zonadagi harakatni frame difference orqali baholash;
- alert paytida bir nechta photo evidence yaratish.

Asosiy fayl:

```text
backend/app/services/camera_ai.py
```

#### Ultralytics YOLO

Ultralytics YOLO AI object detection modeli sifatida ishlatiladi. U camera frame ichidan obyektlarni aniqlaydi.

Bizning MVP’da YOLO quyidagilarni aniqlaydi:

- `person` — odam;
- `cell phone` — telefon;
- `object` — sumka, bottle, handbag, cup va boshqa kichik obyektlar.

Model `.env` orqali tanlanadi:

```env
YOLO_MODEL=yolo11s.pt
```

Yoki yengilroq model:

```env
YOLO_MODEL=yolov8n.pt
```

`yolov8n.pt` tezroq ishlaydi, lekin aniqligi pastroq bo‘lishi mumkin.  
`yolo11s.pt` kuchliroq, lekin kompyuter resursini ko‘proq ishlatadi.

#### Pydantic

Pydantic FastAPI ichida request va response ma’lumotlarini tartibga solish uchun ishlatiladi.

Masalan:

- alert yaratish modeli;
- citizen register modeli;
- citizen report modeli;
- operator login modeli;
- Face ID record modeli.

Pydantic orqali kelayotgan ma’lumotlar struktura bo‘yicha tekshiriladi.

#### Telegram Bot API

Telegram Bot API orqali tizim real vaqtga yaqin ogohlantirish yuboradi.

Telegramga yuboriladigan narsalar:

- AI kamera alert;
- alert evidence rasmi;
- alert geolocation;
- citizen report;
- citizen evidence image;
- operator tasdiqlagan alert haqida xabar.

Telegram logic fayli:

```text
backend/app/services/telegram_service.py
```

`.env` ichida token va chat id yoziladi:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

#### Local JSON storage

Database o‘rniga MVP uchun local JSON storage ishlatiladi. Bu hackathon uchun tez va oddiy yechim.

Local saqlanadigan data:

- ro‘yxatdan o‘tgan fuqarolar;
- Face ID baza recordlari;
- citizen face rasmlari;
- AI evidence rasmlari;
- citizen report rasmlari.

Data folder:

```text
backend/app/data/
```

Ichki struktura:

```text
backend/app/data/evidence/
backend/app/data/citizens/
backend/app/data/faceid/
```

Muhim: bu papkalar GitHubga push qilinmasligi kerak, chunki ichida rasm va local data bo‘ladi.

#### Face matching service

Face matching moduli local FaceNet asosidagi AI pipeline orqali ishlaydi. MTCNN rasm ichidan yuzni topadi, InceptionResnetV1 yuzni embedding vektorga aylantiradi, cosine similarity esa camera’dan olingan yuzni Face ID bazadagi yuzlar bilan solishtirib o‘xshashlik foizini chiqaradi. Agar FaceNet ishlamasa, tizim OpenCV-based fallback similarity usulidan foydalanadi.

Face matching service camera’dan olingan face crop rasmini Face ID bazadagi rasmlar bilan solishtiradi.

Vazifalari:

- alert ichidagi `face_image_url` ni topish;
- Face ID bazadagi barcha odamlar rasmini o‘qish;
- target face bilan bazadagi rasmlar o‘xshashligini hisoblash;
- similarity foizini chiqarish;
- eng yaqin matchni topish;
- match level berish: high / medium / low / no_match.

Face matching fayli:

```text
backend/app/services/face_match_service.py
```

Endpointlar:

```text
GET /face-match/latest
GET /face-match/alerts/{alert_id}
```

Bu demo/local Face Matchmaking hisoblanadi. Natija operator tomonidan tekshirilishi kerak.

---

### Frontend

#### React

React frontendning asosiy UI kutubxonasi sifatida ishlatiladi.

React orqali quyidagi sahifalar va komponentlar qilingan:

- operator login;
- monitoring dashboard;
- live cameras tab;
- AI alerts tab;
- citizen reports tab;
- Face ID baza tab;
- AI Face Matchmaking tab;
- modal / drawer / image preview;
- light mode va dark mode.

Asosiy frontend fayllar:

```text
frontend/src/App.jsx
frontend/src/components/OperatorDashboard.jsx
```

#### Vite

Vite React loyihani tez ishga tushirish va development server uchun ishlatiladi.

Frontend run qilish:

```bash
npm run dev
```

Odatda frontend shu manzilda ochiladi:

```text
http://localhost:5173
```

#### CSS

CSS orqali platformaning UI dizayni qilingan.

CSS vazifalari:

- dark/light mode;
- responsive layout;
- card design;
- alert grid;
- camera grid;
- Face ID baza cardlari;
- Face Matchmaking UI;
- modal va drawer oynalar;
- status badge ranglari;
- operator review buttonlari.

Asosiy CSS fayl:

```text
frontend/src/App.css
```

#### LocalStorage

LocalStorage browser ichida vaqtinchalik ma’lumot saqlash uchun ishlatiladi.

MVP’da LocalStorage orqali quyidagilar saqlanishi mumkin:

- frontend theme: light/dark mode;
- operator/citizen session holati;
- qo‘shilgan camera list;
- user login holati.

Bu production database emas, demo uchun local browser storage hisoblanadi.

#### Fetch API

Fetch API frontend va backend o‘rtasida HTTP so‘rov yuborish uchun ishlatiladi.

Frontend Fetch API orqali:

- backend health check qiladi;
- alertlarni oladi;
- demo alert yaratadi;
- alert statusini yangilaydi;
- citizen report yuboradi;
- Face ID records oladi;
- Face Matchmaking natijasini oladi.

API helper fayl:

```text
frontend/src/api.js
```

---

## AI logic qisqacha

Tizim quyidagi signallarni tekshiradi:

```text
person detected
phone detected
object detected
stationary time
crouch / bending
lower zone motion
object near lower zone
face crop
zoom crop
photo evidence gallery
```

Alert logic:

```text
Oddiy yurib o‘tish → alert yo‘q
5 soniya bir joyda turish → alert
Egilish + pastki zona harakati → alert
Telefon rasm olish pozasi + to‘xtash/egilish → alert
Pastki zona motion yolg‘iz bo‘lsa → alert yo‘q
```

---

## Project structure

```text
mayiz_qani/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── services/
│   │   │   ├── camera_ai.py
│   │   │   ├── telegram_service.py
│   │   │   └── face_match_service.py
│   │   │
│   │   └── data/
│   │       ├── evidence/
│   │       ├── citizens/
│   │       └── faceid/
│   │
│   ├── .env
│   ├── .env.example
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── api.js
│   │   └── components/
│   │       ├── OperatorDashboard.jsx
│   │       └── ...
│   │
│   ├── package.json
│   └── vite.config.js
│
├── .gitignore
└── README.md
```

---

## Backend run qilish

Backend papkaga kiriladi:

```bash
cd backend
```

Virtual environment yaratiladi:

```bash
python -m venv .venv
```

Windows’da activate qilish:

```bash
.venv\Scripts\activate
```

Kerakli paketlar o‘rnatiladi:

```bash
pip install -r requirements.txt
```

Agar Face Matchmaking kerak bo‘lsa:

```bash
pip install facenet-pytorch pillow
```

Backend ishga tushiriladi:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend docs:

```text
http://127.0.0.1:8000/docs
```

---

## Frontend run qilish

Yangi terminalda frontend papkaga kiriladi:

```bash
cd frontend
```

Paketlar o‘rnatiladi:

```bash
npm install
```

Frontend ishga tushiriladi:

```bash
npm run dev
```

Frontend odatda shu manzilda ochiladi:

```text
http://localhost:5173
```

---

## .env namunasi

Backend ichida `.env` file bo‘lishi kerak:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

CAMERA_NAME=Guliston Test Kamerasi 01
CAMERA_LAT=40.4897
CAMERA_LON=68.7842

CAMERA_SOURCE=
CAMERA_INDEX=0

YOLO_MODEL=yolo11s.pt
YOLO_IMGSZ=960
YOLO_CONFIDENCE=0.22

SMART_ZOOM_ENABLED=true
SMART_ZOOM_PADDING=0.55
SMART_ZOOM_ON_PERSON=true

ALERT_ENDPOINT=http://127.0.0.1:8000/alerts

STATIONARY_SECONDS_TO_ALERT=5
INSTANT_ALERT_ENABLED=false

PHOTO_POSE_SECONDS_TO_ALERT=0.7
CROUCH_SECONDS_TO_ALERT=0.8
LOWER_MOTION_THRESHOLD=12

PROCESS_EVERY_N_FRAMES=3
ALERT_COOLDOWN_SECONDS=10

EVIDENCE_BURST_COUNT=6
FRAME_BUFFER_SIZE=120
PHOTO_EVENT_PRE_SECONDS=1.5
PHOTO_EVENT_CAPTURE_SECONDS=2.5

PERSON_MIN_CONFIDENCE=0.45
PERSON_MIN_AREA_RATIO=0.025
PERSON_MAX_AREA_RATIO=0.70
PERSON_MIN_HEIGHT=120
```

---

## Camera sozlash

Laptop camera uchun:

```env
CAMERA_SOURCE=
CAMERA_INDEX=0
```

Agar camera chiqmasa:

```env
CAMERA_INDEX=1
```

yoki:

```env
CAMERA_INDEX=2
```

Hikvision / IP camera uchun RTSP ishlatiladi:

```env
CAMERA_SOURCE=rtsp://admin:password@camera_ip:554/Streaming/Channels/101
```

Sub stream uchun:

```env
CAMERA_SOURCE=rtsp://admin:password@camera_ip:554/Streaming/Channels/102
```

RTSP ishlatayotganda frontendga RTSP yozilmaydi. Frontend doim backend streamni ko‘radi:

```text
http://127.0.0.1:8000/camera/stream
```

---

## Operator login

Demo loginlar:

```text
Username: admin
Password: safedrop123
```

```text
Username: operator
Password: operator123
```

---

## Asosiy backend endpointlar

```text
GET  /health
GET  /alerts
POST /alerts
POST /alerts/demo
PATCH /alerts/{alert_id}/status

GET  /camera/status
GET  /camera/stream

POST /auth/operator-login

POST /citizens/register
POST /citizens/login
GET  /citizens

GET  /citizen/reports
POST /citizen/reports
POST /citizen/reports/upload
PATCH /citizen/reports/{report_id}/status

GET  /faceid/records
POST /faceid/records

GET  /face-match/latest
GET  /face-match/alerts/{alert_id}
```

---

## Demo flow

1. Backend ishga tushiriladi.
2. Frontend ishga tushiriladi.
3. Operator login qiladi.
4. Live camera tab ochiladi.
5. Kamera oldida oddiy yurib o‘tilsa, alert chiqmasligi kerak.
6. Shaxs 5 soniya bir joyda tursa, alert chiqadi.
7. Shaxs egilib, pastki zonaga obyekt qo‘ygandek harakat qilsa, alert chiqadi.
8. Alertda asosiy evidence image, zoom crop, face crop va bir nechta gallery frame ko‘rinadi.
9. Operator alertni tasdiqlaydi yoki rad etadi.
10. Face ID baza orqali camera’dan olingan yuz demo baza bilan solishtiriladi.
11. Telegram botga alert xabari yuboriladi.

---

## GitHubga push qilishda ignore qilinadigan narsalar

Quyidagilar GitHubga chiqmasligi kerak:

```text
.env
.venv/
node_modules/
backend/app/data/evidence/
backend/app/data/citizens/
backend/app/data/faceid/
*.pt
```

`.env.example` GitHubga chiqishi mumkin, lekin ichida token va maxfiy ma’lumotlar bo‘lmasligi kerak.

---

## Muhim eslatma

Bu loyiha hackathon MVP hisoblanadi. AI alertlari yakuniy qaror emas. Har bir alert operator tomonidan tekshirilishi kerak. Face Matchmaking natijalari demo/local baza asosida ishlaydi va real shaxsni huquqiy jihatdan tasdiqlovchi vosita sifatida ishlatilmaydi.
