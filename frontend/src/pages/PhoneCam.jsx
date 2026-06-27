import { useEffect, useRef, useState } from "react";

// Backend always HTTP (no SSL cert), frontend may be HTTPS
const BACKEND_URL = `http://${window.location.hostname}:8001`;

export default function PhoneCam() {
  const videoRef = useRef(null);
  const resultRef = useRef(null);
  const loopRef = useRef(null);
  const streamRef = useRef(null);
  const fpsRef = useRef(0);

  const [state, setState] = useState("idle"); // idle | starting | running | error | stopped
  const [fps, setFps] = useState(0);
  const [detection, setDetection] = useState(null); // { person, risk }
  const [errMsg, setErrMsg] = useState("");

  // FPS counter
  useEffect(() => {
    const t = setInterval(() => {
      setFps(fpsRef.current);
      fpsRef.current = 0;
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearTimeout(loopRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  async function startCamera() {
    setState("starting");
    setErrMsg("");
    try {
      // Try back camera first (environment), fallback to any camera
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        });
      } catch {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      }

      streamRef.current = stream;
      const video = videoRef.current;
      video.srcObject = stream;

      await new Promise((resolve) => {
        video.onloadedmetadata = () => { video.play().catch(() => {}); resolve(); };
        video.oncanplay = () => resolve();
        setTimeout(resolve, 1500);
      });

      setState("running");
      runLoop();
    } catch (e) {
      setState("error");
      setErrMsg(e.message || "Kamera ochilmadi");
    }
  }

  function runLoop() {
    const canvas = document.createElement("canvas");
    let active = true;

    async function tick() {
      if (!active) return;
      const video = videoRef.current;
      if (!video || !video.videoWidth) {
        loopRef.current = setTimeout(tick, 300);
        return;
      }

      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext("2d").drawImage(video, 0, 0);

      await new Promise((res) => {
        canvas.toBlob(async (blob) => {
          if (!blob || !active) { res(); return; }
          try {
            const form = new FormData();
            form.append("file", blob, "frame.jpg");
            const resp = await fetch(`${BACKEND_URL}/camera/analyze`, {
              method: "POST",
              body: form,
              signal: AbortSignal.timeout(3000),
            });
            if (resp.ok && resultRef.current) {
              const url = URL.createObjectURL(await resp.blob());
              const old = resultRef.current.src;
              resultRef.current.src = url;
              if (old?.startsWith("blob:")) URL.revokeObjectURL(old);
              fpsRef.current++;
            }
          } catch {}
          res();
        }, "image/jpeg", 0.75);
      });

      if (active) loopRef.current = setTimeout(tick, 100);
    }

    loopRef.current = setTimeout(tick, 300);

    // Store cleanup fn
    streamRef._stopLoop = () => { active = false; clearTimeout(loopRef.current); };
  }

  function stopCamera() {
    streamRef._stopLoop?.();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (resultRef.current?.src?.startsWith("blob:")) {
      URL.revokeObjectURL(resultRef.current.src);
      resultRef.current.src = "";
    }
    setState("stopped");
  }

  const isRunning = state === "running";
  const isStarting = state === "starting";

  return (
    <div style={{
      minHeight: "100dvh",
      background: "#050a14",
      color: "#e2e8f0",
      display: "flex",
      flexDirection: "column",
      fontFamily: "'Inter', system-ui, sans-serif",
      overflowX: "hidden",
    }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "14px 16px",
        background: "rgba(255,255,255,0.03)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: "linear-gradient(135deg,#2563eb,#7c3aed)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 16,
          }}>🛡</div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#f1f5f9" }}>SafeDrop AI</div>
            <div style={{ fontSize: 10, color: "#475569" }}>Telefon kamera · CAM-02</div>
          </div>
        </div>

        {/* Status badge */}
        <div style={{
          display: "flex", alignItems: "center", gap: 6,
          padding: "4px 10px", borderRadius: 20,
          background: isRunning ? "rgba(34,197,94,0.12)" : isStarting ? "rgba(234,179,8,0.12)" : "rgba(100,116,139,0.12)",
          border: `1px solid ${isRunning ? "rgba(34,197,94,0.3)" : isStarting ? "rgba(234,179,8,0.3)" : "rgba(100,116,139,0.3)"}`,
        }}>
          <div style={{
            width: 7, height: 7, borderRadius: "50%",
            background: isRunning ? "#22c55e" : isStarting ? "#eab308" : "#64748b",
            boxShadow: isRunning ? "0 0 8px #22c55e" : "none",
            animation: isRunning ? "pulse 1.5s infinite" : "none",
          }} />
          <span style={{ fontSize: 11, fontWeight: 600, color: isRunning ? "#4ade80" : isStarting ? "#fde047" : "#94a3b8" }}>
            {isRunning ? `LIVE · ${fps} fps` : isStarting ? "Yuklanmoqda..." : state === "stopped" ? "To'xtatildi" : state === "error" ? "Xato" : "Tayyor"}
          </span>
        </div>
      </div>

      {/* Camera view */}
      <div style={{ flex: 1, position: "relative", background: "#000", minHeight: 300 }}>
        {/* Hidden video */}
        <video ref={videoRef} autoPlay playsInline muted style={{ display: "none" }} />

        {/* AI result image */}
        <img
          ref={resultRef}
          alt=""
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            display: isRunning ? "block" : "none",
          }}
        />

        {/* Idle / starting overlay */}
        {!isRunning && (
          <div style={{
            position: "absolute", inset: 0,
            display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            gap: 12,
          }}>
            {state === "error" ? (
              <>
                <div style={{ fontSize: 40 }}>⚠️</div>
                <div style={{ fontSize: 14, color: "#f87171", textAlign: "center", padding: "0 24px" }}>{errMsg}</div>
                <div style={{ fontSize: 12, color: "#475569", textAlign: "center", padding: "0 24px" }}>
                  Brauzer kamera ruxsatini tekshiring
                </div>
              </>
            ) : isStarting ? (
              <>
                <div style={{ fontSize: 36 }}>📷</div>
                <div style={{ fontSize: 14, color: "#94a3b8" }}>Kamera yoqilmoqda...</div>
              </>
            ) : (
              <>
                <div style={{
                  width: 80, height: 80, borderRadius: 20,
                  background: "rgba(255,255,255,0.05)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 36, marginBottom: 4,
                }}>
                  📷
                </div>
                <div style={{ fontSize: 16, color: "#94a3b8", fontWeight: 500 }}>Kamera o'chiq</div>
                <div style={{ fontSize: 12, color: "#334155", textAlign: "center", padding: "0 32px" }}>
                  Pastdagi tugmani bosib kamerani yoqing
                </div>
              </>
            )}
          </div>
        )}

        {/* Live corner overlay */}
        {isRunning && (
          <div style={{
            position: "absolute", top: 12, left: 12,
            background: "rgba(0,0,0,0.7)",
            backdropFilter: "blur(8px)",
            borderRadius: 8, padding: "4px 10px",
            fontSize: 11, fontWeight: 700, color: "#4ade80",
            display: "flex", alignItems: "center", gap: 6,
            border: "1px solid rgba(34,197,94,0.3)",
          }}>
            <div style={{
              width: 6, height: 6, borderRadius: "50%", background: "#22c55e",
              boxShadow: "0 0 8px #22c55e",
            }} />
            AI LIVE · {fps} fps
          </div>
        )}

        {/* Backend URL top right */}
        {isRunning && (
          <div style={{
            position: "absolute", top: 12, right: 12,
            background: "rgba(0,0,0,0.6)",
            borderRadius: 6, padding: "3px 8px",
            fontSize: 10, color: "#475569",
          }}>
            {BACKEND_URL}
          </div>
        )}
      </div>

      {/* Bottom controls */}
      <div style={{
        padding: "20px 16px 32px",
        background: "rgba(255,255,255,0.02)",
        borderTop: "1px solid rgba(255,255,255,0.06)",
      }}>
        {!isRunning && !isStarting ? (
          <button
            onClick={startCamera}
            style={{
              width: "100%", padding: "16px",
              background: "linear-gradient(135deg, #2563eb, #7c3aed)",
              color: "#fff", border: "none",
              borderRadius: 14, fontSize: 16, fontWeight: 700,
              cursor: "pointer", letterSpacing: 0.5,
              boxShadow: "0 4px 20px rgba(37,99,235,0.4)",
            }}
          >
            📷 Kamerani yoqish
          </button>
        ) : isStarting ? (
          <button disabled style={{
            width: "100%", padding: "16px",
            background: "rgba(255,255,255,0.05)",
            color: "#475569", border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 14, fontSize: 16, fontWeight: 700, cursor: "not-allowed",
          }}>
            Yuklanmoqda...
          </button>
        ) : (
          <button
            onClick={stopCamera}
            style={{
              width: "100%", padding: "16px",
              background: "rgba(239,68,68,0.1)",
              color: "#f87171", border: "1px solid rgba(239,68,68,0.3)",
              borderRadius: 14, fontSize: 16, fontWeight: 700, cursor: "pointer",
            }}
          >
            ⏹ To'xtatish
          </button>
        )}

        <p style={{ textAlign: "center", fontSize: 11, color: "#1e293b", margin: "12px 0 0" }}>
          SafeDrop AI · Backend: {BACKEND_URL}
        </p>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
