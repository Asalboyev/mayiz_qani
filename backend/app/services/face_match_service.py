import json
from pathlib import Path
from typing import Optional, List, Dict, Any

import cv2
import numpy as np
from PIL import Image


FACEID_DIR = Path("app/data/faceid")
FACEID_FILE = FACEID_DIR / "faceid_records.json"

CITIZENS_DIR = Path("app/data/citizens")
EVIDENCE_DIR = Path("app/data/evidence")

FACE_MATCH_THRESHOLD_HIGH = 70.0
FACE_MATCH_THRESHOLD_MEDIUM = 55.0
FACE_MATCH_THRESHOLD_LOW = 40.0

_facenet_ready = False
_facenet_error = None
_mtcnn = None
_resnet = None
_torch = None


def load_faceid_records() -> List[dict]:
    try:
        if not FACEID_FILE.exists():
            return []
        return json.loads(FACEID_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def local_path_from_url(image_url: Optional[str], image_path: Optional[str] = None) -> Optional[Path]:
    if image_path:
        path = Path(image_path)
        if path.exists():
            return path

    if not image_url:
        return None

    clean = image_url.split("?", 1)[0]

    if clean.startswith("/faceid-files/"):
        rel = clean.replace("/faceid-files/", "", 1)
        return FACEID_DIR / rel

    if clean.startswith("/citizen-files/"):
        rel = clean.replace("/citizen-files/", "", 1)
        return CITIZENS_DIR / rel

    if clean.startswith("/evidence/"):
        rel = clean.replace("/evidence/", "", 1)
        return EVIDENCE_DIR / rel

    path = Path(clean)
    if path.exists():
        return path

    return None


def init_facenet():
    global _facenet_ready
    global _facenet_error
    global _mtcnn
    global _resnet
    global _torch

    if _facenet_ready:
        return True

    if _facenet_error:
        return False

    try:
        import torch
        from facenet_pytorch import MTCNN, InceptionResnetV1

        device = "cuda" if torch.cuda.is_available() else "cpu"

        _torch = torch
        _mtcnn = MTCNN(
            image_size=160,
            margin=20,
            keep_all=False,
            post_process=True,
            device=device,
        )
        _resnet = InceptionResnetV1(pretrained="vggface2").eval().to(device)

        _facenet_ready = True
        return True
    except Exception as error:
        _facenet_error = str(error)
        return False


def get_facenet_embedding(image_path: Path):
    if not init_facenet():
        return None

    try:
        image = Image.open(image_path).convert("RGB")
        face_tensor = _mtcnn(image)

        if face_tensor is None:
            return None

        with _torch.no_grad():
            embedding = _resnet(face_tensor.unsqueeze(0))
            embedding = _torch.nn.functional.normalize(embedding, p=2, dim=1)

        return embedding.cpu().numpy()[0]
    except Exception:
        return None


def cosine_percent(embedding_a, embedding_b) -> float:
    if embedding_a is None or embedding_b is None:
        return 0.0

    score = float(np.dot(embedding_a, embedding_b))
    score = max(0.0, min(1.0, score))

    return round(score * 100.0, 1)


def opencv_fingerprint(image_path: Path):
    image = cv2.imread(str(image_path))

    if image is None:
        return None

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (160, 160))
    gray = cv2.equalizeHist(gray)

    hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
    cv2.normalize(hist, hist)

    return hist


def opencv_similarity_percent(path_a: Path, path_b: Path) -> float:
    hist_a = opencv_fingerprint(path_a)
    hist_b = opencv_fingerprint(path_b)

    if hist_a is None or hist_b is None:
        return 0.0

    score = float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL))
    score = max(0.0, min(1.0, score))

    return round(score * 100.0, 1)


def match_level(score: float) -> str:
    if score >= FACE_MATCH_THRESHOLD_HIGH:
        return "high"
    if score >= FACE_MATCH_THRESHOLD_MEDIUM:
        return "medium"
    if score >= FACE_MATCH_THRESHOLD_LOW:
        return "low"
    return "no_match"


def match_label(level: str) -> str:
    labels = {
        "high": "Kuchli moslik",
        "medium": "O‘xshashlik bor, operator tekshirsin",
        "low": "Past moslik",
        "no_match": "Moslik topilmadi",
    }

    return labels.get(level, level)


def match_face_against_database(
    target_face_image_url: Optional[str] = None,
    target_face_image_path: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    target_path = local_path_from_url(
        image_url=target_face_image_url,
        image_path=target_face_image_path,
    )

    if target_path is None or not target_path.exists():
        return {
            "ok": False,
            "engine": "none",
            "error": "Target face image topilmadi",
            "target_face_image_url": target_face_image_url,
            "matches": [],
            "best_match": None,
        }

    records = load_faceid_records()

    if not records:
        return {
            "ok": True,
            "engine": "empty_database",
            "error": None,
            "target_face_image_url": target_face_image_url,
            "matches": [],
            "best_match": None,
        }

    target_embedding = get_facenet_embedding(target_path)
    use_facenet = target_embedding is not None

    matches = []

    for record in records:
        record_image_url = record.get("face_image_url")
        record_path = local_path_from_url(record_image_url)

        if record_path is None or not record_path.exists():
            continue

        if use_facenet:
            record_embedding = get_facenet_embedding(record_path)
            score = cosine_percent(target_embedding, record_embedding)
            engine = "facenet_pytorch"
        else:
            score = opencv_similarity_percent(target_path, record_path)
            engine = "opencv_fallback"

        level = match_level(score)

        matches.append(
            {
                "id": record.get("id"),
                "full_name": record.get("full_name"),
                "phone": record.get("phone"),
                "source": record.get("source"),
                "risk_level": record.get("risk_level"),
                "note": record.get("note"),
                "face_image_url": record_image_url,
                "score": score,
                "match_level": level,
                "match_label": match_label(level),
                "engine": engine,
            }
        )

    matches.sort(key=lambda item: item["score"], reverse=True)
    matches = matches[:limit]

    best_match = matches[0] if matches else None

    return {
        "ok": True,
        "engine": "facenet_pytorch" if use_facenet else "opencv_fallback",
        "facenet_error": _facenet_error,
        "target_face_image_url": target_face_image_url,
        "target_face_image_path": str(target_path),
        "matches": matches,
        "best_match": best_match,
    }