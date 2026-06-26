import { useEffect, useRef, useState } from "react";
import { api } from "../api";

function formatUzPhone(value) {
  let digits = String(value || "").replace(/\D/g, "");

  if (digits.startsWith("998")) {
    digits = digits.slice(3);
  }

  digits = digits.slice(0, 9);

  return `+998${digits}`;
}

function Landing({ onCitizenLogin, onOperator }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const [mode, setMode] = useState("register");

  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("+998");

  const [faceImage, setFaceImage] = useState("");
  const [cameraActive, setCameraActive] = useState(false);
  const [videoReady, setVideoReady] = useState(false);
  const [cameraError, setCameraError] = useState("");

  const [loginPhone, setLoginPhone] = useState("+998");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function startFaceCamera() {
    setError("");
    setCameraError("");
    setVideoReady(false);

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setCameraError("Brauzer kamera funksiyasini qo‘llab-quvvatlamaydi.");
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "user",
          width: { ideal: 640 },
          height: { ideal: 480 },
        },
        audio: false,
      });

      streamRef.current = stream;
      setCameraActive(true);

      setTimeout(async () => {
        if (!videoRef.current) return;

        videoRef.current.srcObject = stream;

        try {
          await videoRef.current.play();
        } catch (playError) {
          console.error(playError);
          setCameraError("Video ishga tushmadi. Browser permissionni tekshiring.");
        }
      }, 100);
    } catch (err) {
      console.error(err);
      setCameraError("Kamera ruxsati berilmadi yoki kamera topilmadi.");
      setCameraActive(false);
      setVideoReady(false);
    }
  }

  function stopFaceCamera() {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setCameraActive(false);
    setVideoReady(false);
  }

  function captureFace() {
    setError("");

    const video = videoRef.current;

    if (!video) {
      setError("Kamera topilmadi.");
      return;
    }

    if (!videoReady || video.videoWidth === 0 || video.videoHeight === 0) {
      setError("Kamera hali tayyor emas. 1-2 soniya kutib qayta urinib ko‘ring.");
      return;
    }

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");

    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const image = canvas.toDataURL("image/jpeg", 0.9);

    setFaceImage(image);
    localStorage.setItem("safedrop_last_face_image", image);

    stopFaceCamera();
  }

  function resetFace() {
    setFaceImage("");
    setCameraError("");
    setError("");
    localStorage.removeItem("safedrop_last_face_image");
  }

  async function registerCitizen(e) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (!fullName.trim()) {
        throw new Error("Ism familiya kiriting");
      }

      if (!phone || phone.length < 13) {
        throw new Error("Telefon raqamni to‘liq kiriting");
      }

      if (!faceImage) {
        throw new Error("Demo FaceID olish kerak");
      }

      const data = await api.registerCitizen({
        full_name: fullName.trim(),
        phone,
        face_image: faceImage,
      });

      const user = {
        ...data.citizen,
        face_image: `${api.base}${data.citizen.face_image_url}`,
      };

      localStorage.setItem("safedrop_citizen", JSON.stringify(user));
      localStorage.setItem("safedrop_face_id", user.face_id);
      localStorage.setItem("safedrop_face_image", user.face_image);

      onCitizenLogin(user);
    } catch (err) {
      setError(err.message || "Ro‘yxatdan o‘tishda xato");
    } finally {
      setLoading(false);
    }
  }

  async function loginCitizen(e) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (!loginPhone || loginPhone.length < 13) {
        throw new Error("Telefon raqamni to‘liq kiriting");
      }

      const data = await api.loginCitizen(loginPhone);

      const user = {
        ...data.citizen,
        face_image: `${api.base}${data.citizen.face_image_url}`,
      };

      localStorage.setItem("safedrop_citizen", JSON.stringify(user));
      localStorage.setItem("safedrop_face_id", user.face_id);
      localStorage.setItem("safedrop_face_image", user.face_image);

      onCitizenLogin(user);
    } catch (err) {
      setError(err.message || "Login qilishda xato");
    } finally {
      setLoading(false);
    }
  }

  function switchMode(nextMode) {
    setMode(nextMode);
    setError("");
    setCameraError("");
    stopFaceCamera();
  }

  useEffect(() => {
    return () => {
      stopFaceCamera();
    };
  }, []);

  return (
    <div className="landing">
      <div className="landing-box auth-box">
        <div className="logo">SD</div>

        <h1>Mayiz Qani</h1>
        

        <div className="auth-tabs">
          <button
            type="button"
            className={mode === "register" ? "active" : ""}
            onClick={() => switchMode("register")}
          >
            Ro‘yxatdan o‘tish
          </button>

          <button
            type="button"
            className={mode === "login" ? "active" : ""}
            onClick={() => switchMode("login")}
          >
            Fuqaro login
          </button>
        </div>

        {mode === "register" ? (
          <form className="card form-card wide" onSubmit={registerCitizen}>
           
            <div className="two-col">
              <label>
                Ism familiya
                <input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Masalan: Ali Karimov"
                />
              </label>

              <label>
                Telefon raqam
                <input
                  value={phone}
                  onChange={(e) => setPhone(formatUzPhone(e.target.value))}
                  placeholder="+998901234567"
                />
              </label>
            </div>

            <div className="faceid-box">
              <div className="faceid-head">
                <div>
                  <strong>Demo FaceID</strong>
                  <p>Yuzingizni kamera orqali tasdiqlang.</p>
                </div>

                {faceImage && <span className="face-check">✓ Olingan</span>}
              </div>

              {!faceImage && (
                <>
                  <div className="face-camera">
                    <video
                      ref={videoRef}
                      autoPlay
                      playsInline
                      muted
                      onLoadedMetadata={() => setVideoReady(true)}
                      className={cameraActive ? "face-video active" : "face-video"}
                    />

                    {!cameraActive && (
                      <div className="face-placeholder">
                        <span>FaceID kamera oynasi</span>
                      </div>
                    )}
                  </div>

                  {cameraError && <div className="error">{cameraError}</div>}

                  <div className="face-actions">
                    {!cameraActive ? (
                      <button
                        type="button"
                        className="secondary"
                        onClick={startFaceCamera}
                      >
                        FaceID olish
                      </button>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="primary"
                          onClick={captureFace}
                          disabled={!videoReady}
                        >
                          {videoReady ? "Rasmga olish" : "Kamera tayyorlanmoqda..."}
                        </button>

                        <button
                          type="button"
                          className="secondary"
                          onClick={stopFaceCamera}
                        >
                          Bekor qilish
                        </button>
                      </>
                    )}
                  </div>
                </>
              )}

              {faceImage && (
                <div className="face-preview">
                  <img src={faceImage} alt="Demo FaceID" />

                  <div>
                    <strong>FaceID tayyor</strong>
                    <p>Rasm ro‘yxatdan o‘tishda backendga saqlanadi.</p>

                    <button
                      type="button"
                      className="secondary"
                      onClick={resetFace}
                    >
                      Qayta olish
                    </button>
                  </div>
                </div>
              )}
            </div>

            {error && <div className="error">{error}</div>}

            <button className="primary" disabled={loading}>
              {loading ? "Saqlanmoqda..." : "Ro‘yxatdan o‘tish"}
            </button>
          </form>
        ) : (
          <form className="card form-card wide" onSubmit={loginCitizen}>
            <h2>Fuqaro login</h2>
            <p>Ro‘yxatdan o‘tgan telefon raqam orqali kiring.</p>

            <label>
              Telefon raqam
              <input
                value={loginPhone}
                onChange={(e) => setLoginPhone(formatUzPhone(e.target.value))}
                placeholder="+998901234567"
              />
            </label>

            {error && <div className="error">{error}</div>}

            <button className="primary" disabled={loading}>
              {loading ? "Tekshirilmoqda..." : "Kirish"}
            </button>
          </form>
        )}

        <div className="operator-entry">
          <span>Cybersecurity xodimimisiz?</span>
          <button type="button" onClick={onOperator}>
            Operator login
          </button>
        </div>
      </div>
    </div>
  );
}

export default Landing;