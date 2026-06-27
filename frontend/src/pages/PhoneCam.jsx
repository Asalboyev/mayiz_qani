import { useEffect, useRef, useState } from "react";
import { api } from "../api";

export default function PhoneCam() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const resultRef = useRef(null);
  const loopRef = useRef(null);
  const streamRef = useRef(null);

  const [status, setStatus] = useState("Boshlash uchun tugmani bosing");
  const [running, setRunning] = useState(false);
  const [fps, setFps] = useState(0);
  const fpsCounter = useRef(0);

  useEffect(() => {
    const t = setInterval(() => {
      setFps(fpsCounter.current);
      fpsCounter.current = 0;
    }, 1000);
    return () => clearInterval(t);
  }, []);

  async function startCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: 1280, height: 720 },
        audio: false,
      });
      streamRef.current = stream;
      const video = videoRef.current;
      video.srcObject = stream;
      video.onloadedmetadata = () => {
        video.play();
        startLoop();
        setRunning(true);
        setStatus("AI analiz davom etmoqda...");
      };
    } catch {
      setStatus("Kamera ruxsati berilmadi");
    }
  }

  function startLoop() {
    const canvas = document.createElement("canvas");
    canvasRef.current = canvas;
    let active = true;

    async function loop() {
      if (!active || !videoRef.current) return;
      const video = videoRef.current;
      if (!video.videoWidth) { loopRef.current = setTimeout(loop, 200); return; }

      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext("2d").drawImage(video, 0, 0);

      canvas.toBlob(async (blob) => {
        if (!blob || !active) return;
        try {
          const form = new FormData();
          form.append("file", blob, "frame.jpg");
          const res = await fetch(`${api.base}/camera/analyze`, { method: "POST", body: form });
          if (res.ok && resultRef.current) {
            const url = URL.createObjectURL(await res.blob());
            const old = resultRef.current.src;
            resultRef.current.src = url;
            if (old?.startsWith("blob:")) URL.revokeObjectURL(old);
            fpsCounter.current++;
          }
        } catch {}
        if (active) loopRef.current = setTimeout(loop, 120);
      }, "image/jpeg", 0.8);
    }

    loopRef.current = setTimeout(loop, 300);
    return () => { active = false; clearTimeout(loopRef.current); };
  }

  function stopCamera() {
    clearTimeout(loopRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    setRunning(false);
    setStatus("To'xtatildi");
  }

  return (
    <div style={{
      minHeight: "100vh", background: "#0a0f1a", color: "#e2e8f0",
      display: "flex", flexDirection: "column", alignItems: "center",
      padding: "16px", fontFamily: "sans-serif",
    }}>
      <h2 style={{ margin: "0 0 4px", fontSize: 18 }}>SafeDrop AI · Telefon kamera</h2>
      <p style={{ color: "#64748b", fontSize: 13, margin: "0 0 16px" }}>{status}</p>

      {/* Hidden video for capture */}
      <video ref={videoRef} autoPlay playsInline muted style={{ display: "none" }} />

      {/* AI result */}
      <div style={{ width: "100%", maxWidth: 480, position: "relative" }}>
        <img
          ref={resultRef}
          alt="AI natija"
          style={{
            width: "100%", borderRadius: 12,
            background: "#111827", minHeight: 200,
            display: "block",
          }}
        />
        {running && (
          <div style={{
            position: "absolute", top: 8, left: 8,
            background: "rgba(0,0,0,0.7)", borderRadius: 6,
            padding: "2px 8px", fontSize: 11, color: "#4ade80", fontWeight: 700,
          }}>
            ● AI LIVE · {fps} fps
          </div>
        )}
      </div>

      <div style={{ marginTop: 20, display: "flex", gap: 12 }}>
        {!running ? (
          <button onClick={startCamera} style={{
            padding: "12px 32px", background: "#2563eb", color: "#fff",
            border: "none", borderRadius: 10, fontSize: 16, cursor: "pointer",
          }}>
            📷 Kamerani yoqish
          </button>
        ) : (
          <button onClick={stopCamera} style={{
            padding: "12px 32px", background: "#dc2626", color: "#fff",
            border: "none", borderRadius: 10, fontSize: 16, cursor: "pointer",
          }}>
            ⏹ To'xtatish
          </button>
        )}
      </div>

      <p style={{ fontSize: 11, color: "#334155", marginTop: 20, textAlign: "center" }}>
        Bu sahifa telefon kamerasini AI ga ulaydi.<br />
        Backend: {api.base}
      </p>
    </div>
  );
}
