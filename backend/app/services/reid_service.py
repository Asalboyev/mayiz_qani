"""
Multi-Camera Person Re-Identification (Re-ID) service.

Lightweight approach using color histogram + spatial layout features.
No extra ML dependencies — works with OpenCV + NumPy only.

Each detected person gets an appearance feature vector extracted from their
bounding-box crop. When a new person arrives we compare against all active
tracks across all cameras using cosine similarity and decide if it's a
known or new person.
"""

import time
import uuid
import threading
from typing import Optional, List, Dict, Any, Tuple

import cv2
import numpy as np

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

REID_SIMILARITY_THRESHOLD = 0.72   # cosine sim ≥ this → same person
REID_TRACK_TTL_SECONDS     = 120   # forget person if not seen for 2 min
REID_MAX_TRACKS            = 200   # memory guard

# ─────────────────────────────────────────────
# INTERNAL STATE
# ─────────────────────────────────────────────

_lock   = threading.Lock()

# track_id → {
#   "track_id":   str,
#   "camera_ids": [str, ...],          # all cameras this person was seen on
#   "features":   [np.ndarray, ...],   # rolling window of feature vectors
#   "first_seen": float,
#   "last_seen":  float,
#   "sightings":  [{camera_id, ts, bbox}, ...]
# }
_tracks: Dict[str, Dict[str, Any]] = {}


# ─────────────────────────────────────────────
# FEATURE EXTRACTION
# ─────────────────────────────────────────────

def _extract_features(crop: np.ndarray) -> Optional[np.ndarray]:
    """
    Extract a compact appearance descriptor from a person crop.
    Returns a 1-D float32 feature vector, or None if crop is too small.
    """
    if crop is None or crop.size == 0:
        return None
    h, w = crop.shape[:2]
    if h < 32 or w < 16:
        return None

    # Resize to fixed patch so feature dim is constant
    patch = cv2.resize(crop, (64, 128))

    # --- Color histogram in HSV (robust to lighting) ---
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)

    # Split body into 6 horizontal stripes for spatial colour layout
    stripes = np.array_split(hsv, 6, axis=0)
    color_hist = []
    for stripe in stripes:
        h_hist = cv2.calcHist([stripe], [0], None, [16], [0, 180]).flatten()
        s_hist = cv2.calcHist([stripe], [1], None, [8],  [0, 256]).flatten()
        color_hist.append(h_hist)
        color_hist.append(s_hist)

    color_feat = np.concatenate(color_hist).astype(np.float32)

    # --- Simple texture: LBP-like gradient magnitude histogram ---
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx**2 + gy**2)
    tex_hist = np.histogram(mag, bins=16, range=(0, 255))[0].astype(np.float32)

    feat = np.concatenate([color_feat, tex_hist])

    # L2 normalise
    norm = np.linalg.norm(feat)
    if norm < 1e-6:
        return None
    return feat / norm


# ─────────────────────────────────────────────
# MATCHING
# ─────────────────────────────────────────────

def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))   # both already L2-normalised


def _match_features(query: np.ndarray) -> Optional[str]:
    """
    Return track_id of best matching active track, or None if no good match.
    """
    best_id  = None
    best_sim = REID_SIMILARITY_THRESHOLD  # minimum to accept

    now = time.time()
    for tid, track in _tracks.items():
        if now - track["last_seen"] > REID_TRACK_TTL_SECONDS:
            continue
        # Average similarity against stored feature window
        sims = [_cosine_sim(query, f) for f in track["features"][-8:]]
        sim  = float(np.mean(sims)) if sims else 0.0
        if sim > best_sim:
            best_sim = sim
            best_id  = tid

    return best_id


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def update_track(
    frame_bgr: np.ndarray,
    bbox: Tuple[int, int, int, int],   # x1, y1, x2, y2
    camera_id: str,
) -> Dict[str, Any]:
    """
    Given a person crop, find or create a Re-ID track.

    Returns a dict:
      {
        "track_id":    str,
        "is_new":      bool,       # True → first time we see this person
        "cross_camera": bool,      # True → same person seen on different camera
        "camera_ids":  [str, ...],
        "first_seen":  float,
        "last_seen":   float,
        "sightings":   int,
      }
    """
    x1, y1, x2, y2 = bbox
    crop = frame_bgr[y1:y2, x1:x2]
    feat = _extract_features(crop)

    now = time.time()

    with _lock:
        # Purge stale tracks (memory guard)
        stale = [tid for tid, t in _tracks.items()
                 if now - t["last_seen"] > REID_TRACK_TTL_SECONDS]
        for tid in stale:
            del _tracks[tid]

        if len(_tracks) > REID_MAX_TRACKS:
            # Remove oldest
            oldest = sorted(_tracks, key=lambda t: _tracks[t]["last_seen"])
            for tid in oldest[:20]:
                del _tracks[tid]

        matched_id = _match_features(feat) if feat is not None else None

        if matched_id:
            track = _tracks[matched_id]
            is_new = False
            cross_camera = camera_id not in track["camera_ids"]
            if cross_camera:
                track["camera_ids"].append(camera_id)
            if feat is not None:
                track["features"].append(feat)
                if len(track["features"]) > 16:
                    track["features"].pop(0)
            track["last_seen"] = now
            track["sightings"].append({
                "camera_id": camera_id,
                "ts": now,
                "bbox": list(bbox),
            })
            return {
                "track_id":    matched_id,
                "is_new":      False,
                "cross_camera": cross_camera,
                "camera_ids":  track["camera_ids"][:],
                "first_seen":  track["first_seen"],
                "last_seen":   now,
                "sightings":   len(track["sightings"]),
            }
        else:
            # New person
            tid = str(uuid.uuid4())[:8]
            _tracks[tid] = {
                "track_id":  tid,
                "camera_ids": [camera_id],
                "features":   [feat] if feat is not None else [],
                "first_seen": now,
                "last_seen":  now,
                "sightings":  [{
                    "camera_id": camera_id,
                    "ts": now,
                    "bbox": list(bbox),
                }],
            }
            return {
                "track_id":    tid,
                "is_new":      True,
                "cross_camera": False,
                "camera_ids":  [camera_id],
                "first_seen":  now,
                "last_seen":   now,
                "sightings":   1,
            }


def get_all_tracks() -> List[Dict[str, Any]]:
    """Return all active (non-expired) tracks for the /reid/tracks endpoint."""
    now = time.time()
    result = []
    with _lock:
        for tid, t in _tracks.items():
            if now - t["last_seen"] > REID_TRACK_TTL_SECONDS:
                continue
            result.append({
                "track_id":   tid,
                "camera_ids": t["camera_ids"][:],
                "first_seen": t["first_seen"],
                "last_seen":  t["last_seen"],
                "sightings":  len(t["sightings"]),
                "cross_camera": len(set(t["camera_ids"])) > 1,
                "last_sighting": t["sightings"][-1] if t["sightings"] else None,
            })
    result.sort(key=lambda x: x["last_seen"], reverse=True)
    return result


def clear_tracks() -> int:
    """Clear all tracks. Returns count of cleared tracks."""
    with _lock:
        n = len(_tracks)
        _tracks.clear()
    return n
