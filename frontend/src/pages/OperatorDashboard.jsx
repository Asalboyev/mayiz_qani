import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

function statusText(status) {
  const map = {
    operator_tekshiruvi_talab_qilinadi: "Ko‘rib chiqish kerak",
    tasdiqlandi: "Tasdiqlandi",
    rad_etildi: "Rad etildi",
    new: "Yangi",
    reviewing: "Ko‘rib chiqilmoqda",
    confirmed: "Tasdiqlandi",
    rejected: "Rad etildi",
  };

  return map[status] || status;
}

function statusClass(status) {
  const map = {
    new: "status-new",
    reviewing: "status-reviewing",
    confirmed: "status-confirmed",
    rejected: "status-rejected",
    operator_tekshiruvi_talab_qilinadi: "status-reviewing",
    tasdiqlandi: "status-confirmed",
    rad_etildi: "status-rejected",
  };

  return map[status] || "status-new";
}

function formatTime(value) {
  if (!value) return "-";
  return String(value).replace("T", " ");
}

const defaultCameras = [
  {
    id: "CAM-01",
    name: "Guliston test kamerasi",
    location: "Guliston test hududi",
    streamUrl: `${api.base}/camera/stream`,
    status: "online",
  },
];

function loadSavedCameras() {
  try {
    const saved = localStorage.getItem("mayizqani_cameras");
    if (!saved) return defaultCameras;

    const parsed = JSON.parse(saved);
    return Array.isArray(parsed) && parsed.length > 0 ? parsed : defaultCameras;
  } catch {
    return defaultCameras;
  }
}

function OperatorDashboard({ onLogout }) {
  const [tab, setTab] = useState("ai");
  const [health, setHealth] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [reports, setReports] = useState([]);
  const [faceRecords, setFaceRecords] = useState([]);
  const [faceFilter, setFaceFilter] = useState("all");
  const [showFaceForm, setShowFaceForm] = useState(false);
  const [newFace, setNewFace] = useState({
    full_name: "",
    phone: "",
    risk_level: "unknown",
    note: "",
    face_image: "",
  });
  const [reportFilter, setReportFilter] = useState("all");

  const [cameras, setCameras] = useState(loadSavedCameras);
  const [selectedCameraId, setSelectedCameraId] = useState("CAM-01");
  const [showCameraForm, setShowCameraForm] = useState(false);
  const [zoomCamera, setZoomCamera] = useState(null);

  const [selectedAlert, setSelectedAlert] = useState(null);
  const [selectedReport, setSelectedReport] = useState(null);
  const [imageModal, setImageModal] = useState(null);

  const [reviewModal, setReviewModal] = useState(null);
  const [reviewNote, setReviewNote] = useState("");

  const [faceMatch, setFaceMatch] = useState(null);
  const [faceMatchLoading, setFaceMatchLoading] = useState(false);

  const [newCamera, setNewCamera] = useState({
    name: "",
    location: "",
    streamUrl: "",
  });

  const selectedCamera = useMemo(() => {
    return cameras.find((camera) => camera.id === selectedCameraId) || cameras[0];
  }, [cameras, selectedCameraId]);

  const reportCounts = useMemo(() => {
    return {
      all: reports.length,
      new: reports.filter((item) => item.status === "new").length,
      reviewing: reports.filter((item) => item.status === "reviewing").length,
      confirmed: reports.filter((item) => item.status === "confirmed").length,
      rejected: reports.filter((item) => item.status === "rejected").length,
    };
  }, [reports]);

  const filteredReports = useMemo(() => {
    if (reportFilter === "all") {
      return reports;
    }

    return reports.filter((report) => report.status === reportFilter);
  }, [reports, reportFilter]);

  async function loadData() {
    try {
      const [healthData, alertData, reportData, faceData] = await Promise.all([
        api.health(),
        api.getAlerts(),
        api.getCitizenReports(),
        api.getFaceIdRecords(),
      ]);

      const nextAlerts = alertData.alerts || [];
      const nextReports = reportData.reports || [];

      setHealth(healthData);
      setAlerts(nextAlerts);
      setReports(nextReports);
      setFaceRecords(faceData.records || []);

      if (selectedAlert) {
        const freshAlert = nextAlerts.find((item) => item.id === selectedAlert.id);
        if (freshAlert) setSelectedAlert(freshAlert);
      }

      if (selectedReport) {
        const freshReport = nextReports.find((item) => item.id === selectedReport.id);
        if (freshReport) setSelectedReport(freshReport);
      }
    } catch (err) {
      console.error(err);
    }
  }
  async function loadLatestFaceMatch() {
  setFaceMatchLoading(true);

  try {
    const data = await api.getLatestFaceMatch();
    setFaceMatch(data);
  } catch (error) {
    console.error(error);
    setFaceMatch({
      ok: false,
      error: error.message || "Face match yuklanmadi",
      result: null,
    });
  } finally {
    setFaceMatchLoading(false);
  }
}

async function loadFaceMatchForAlert(alertId) {
  setFaceMatchLoading(true);

  try {
    const data = await api.getFaceMatchForAlert(alertId);
    setFaceMatch(data);
    setTab("faceMatch");
    setSelectedAlert(null);
  } catch (error) {
    alert("Face match qilishda xato: " + error.message);
  } finally {
    setFaceMatchLoading(false);
  }
}

  async function demoAlert() {
    await api.createDemoAlert();
    await loadData();
  }

  function openReviewModal(kind, item, status) {
    setReviewModal({
      kind,
      id: item.id,
      status,
      title:
        kind === "alert"
          ? `AI alert: ${item.camera_name}`
          : `Fuqaro xabari: ${item.location_text || "Joylashuv ko‘rsatilmagan"}`,
    });

    setReviewNote("");
  }

  async function submitReview() {
    if (!reviewModal) return;

    if (reviewModal.kind === "alert") {
      await api.updateAlertStatus(
        reviewModal.id,
        reviewModal.status,
        reviewNote,
        "admin"
      );
    }

    if (reviewModal.kind === "report") {
      await api.updateCitizenReportStatus(
        reviewModal.id,
        reviewModal.status,
        reviewNote,
        "admin"
      );
    }

    setReviewModal(null);
    setReviewNote("");
    await loadData();
  }

  function addCamera(e) {
    e.preventDefault();

    const nextNumber = cameras.length + 1;
    const cameraId = `CAM-${String(Date.now()).slice(-5)}`;

    const camera = {
      id: cameraId,
      name: newCamera.name.trim() || `Camera ${nextNumber}`,
      location: newCamera.location.trim() || "Joylashuv ko‘rsatilmagan",
      streamUrl: newCamera.streamUrl.trim() || `${api.base}/camera/stream`,
      status: "online",
    };

    setCameras((prev) => [...prev, camera]);
    setSelectedCameraId(camera.id);

    setNewCamera({
      name: "",
      location: "",
      streamUrl: "",
    });

    setShowCameraForm(false);
  }

  function deleteCamera(cameraId) {
    if (cameras.length === 1) {
      alert("Kamida bitta kamera qolishi kerak");
      return;
    }

    const nextCameras = cameras.filter((camera) => camera.id !== cameraId);
    setCameras(nextCameras);

    if (selectedCameraId === cameraId) {
      setSelectedCameraId(nextCameras[0]?.id || "CAM-01");
    }
  }

  useEffect(() => {
    loadData();
    const timer = setInterval(loadData, 3000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    localStorage.setItem("mayizqani_cameras", JSON.stringify(cameras));
  }, [cameras]);

  return (
    <div className="dashboard">
      <aside className="dash-sidebar">
        <h2>Mayiz Qani</h2>
        <p>Operator console</p>

        <button className={tab === "ai" ? "active" : ""} onClick={() => setTab("ai")}>
          AI alerts
        </button>

        <button
          className={tab === "cameras" ? "active" : ""}
          onClick={() => setTab("cameras")}
        >
          Live cameras
        </button>

        <button
          className={tab === "citizen" ? "active" : ""}
          onClick={() => setTab("citizen")}
        >
          Citizen reports
        </button>

        <button
          className={tab === "faceid" ? "active" : ""}
          onClick={() => setTab("faceid")}
        >
          Face ID baza
        </button>
        <button
  className={tab === "faceMatch" ? "active" : ""}
  onClick={() => {
    setTab("faceMatch");
    loadLatestFaceMatch();
  }}
>
  AI Face Matchmaking
</button>

        <button onClick={onLogout}>Chiqish</button>
      </aside>

      <main className="dash-main">
        <header className="dash-header">
          <div>
            <h1>Monitoring paneli</h1>
            <p>{health?.ok ? "Backend online" : "Backend offline"}</p>
          </div>

          <button className="primary small" onClick={demoAlert}>
            Demo alert
          </button>
        </header>

        <section className="stats">
          <div className="stat">
            <span>AI alertlar</span>
            <strong>{alerts.length}</strong>
          </div>

          <div className="stat">
            <span>Live kameralar</span>
            <strong>{cameras.length}</strong>
          </div>

          <div className="stat">
            <span>Fuqaro xabarlari</span>
            <strong>{reports.length}</strong>
          </div>
        </section>

        {tab === "ai" && (
          <div className="card">
            <div className="section-head">
              <div>
                <h3>AI alertlar</h3>
                <p>Kameralar orqali avtomatik aniqlangan shubhali holatlar.</p>
              </div>
            </div>

            {alerts.length === 0 ? (
              <p className="muted">Hozircha alert yo‘q.</p>
            ) : (
              <div className="alert-grid">
                {alerts.map((alert) => (
                  <button
                    className="alert-card"
                    key={alert.id}
                    onClick={() => setSelectedAlert(alert)}
                  >
                    {alert.evidence_image_url ? (
                      <img
                        src={`${api.base}${alert.evidence_image_url}`}
                        alt="evidence"
                        onClick={(e) => {
                          e.stopPropagation();
                          setImageModal(`${api.base}${alert.evidence_image_url}`);
                        }}
                      />
                    ) : (
                      <div className="no-image">No evidence</div>
                    )}

                    <div className="alert-card-body">
                      <div className="item-top">
                        <strong>{alert.camera_name}</strong>
                        <span>{alert.confidence}%</span>
                      </div>

                      <p>{alert.action}</p>

                      <div className="mini-meta">
                        <span>{formatTime(alert.created_at)}</span>
                        <span className={`status-badge ${statusClass(alert.status)}`}>
                          {statusText(alert.status)}
                        </span>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "cameras" && (
          <section className="camera-page">
            <div className="card">
              <div className="section-head">
                <div>
                  <h3>Live cameras</h3>
                  <p>Kameralarni tanlang, kuzating yoki katta oynada oching.</p>
                </div>

                <button
                  className="secondary"
                  onClick={() => setShowCameraForm((prev) => !prev)}
                >
                  {showCameraForm ? "Yopish" : "Camera qo‘shish"}
                </button>
              </div>

              {showCameraForm && (
                <form className="camera-form" onSubmit={addCamera}>
                  <div className="two-col">
                    <label>
                      Camera nomi
                      <input
                        value={newCamera.name}
                        onChange={(e) =>
                          setNewCamera((prev) => ({
                            ...prev,
                            name: e.target.value,
                          }))
                        }
                        placeholder="Masalan: Park kirish kamerasi"
                      />
                    </label>

                    <label>
                      Joylashuv
                      <input
                        value={newCamera.location}
                        onChange={(e) =>
                          setNewCamera((prev) => ({
                            ...prev,
                            location: e.target.value,
                          }))
                        }
                        placeholder="Masalan: Guliston park"
                      />
                    </label>
                  </div>

                  <label>
                    Stream URL
                    <input
                      value={newCamera.streamUrl}
                      onChange={(e) =>
                        setNewCamera((prev) => ({
                          ...prev,
                          streamUrl: e.target.value,
                        }))
                      }
                      placeholder="Bo‘sh qoldirilsa default local stream ishlaydi"
                    />
                  </label>

                  <button className="primary">Saqlash</button>
                </form>
              )}
            </div>

            <div className="camera-layout">
              <div className="card">
                <h3>Camera list</h3>

                <div className="camera-list">
                  {cameras.map((camera) => (
                    <div
                      key={camera.id}
                      className={
                        selectedCamera?.id === camera.id
                          ? "camera-card active"
                          : "camera-card"
                      }
                      onClick={() => setSelectedCameraId(camera.id)}
                    >
                      <div className="camera-card-top">
                        <div>
                          <strong>{camera.name}</strong>
                          <p>{camera.location}</p>
                        </div>

                        <span>{camera.id}</span>
                      </div>

                      <div className="camera-card-bottom">
                        <small className={camera.status === "online" ? "online" : "offline"}>
                          {camera.status}
                        </small>

                        <button
                          className="delete-camera"
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteCamera(camera.id);
                          }}
                        >
                          O‘chirish
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card camera-main-card">
                <div className="section-head">
                  <div>
                    <h3>{selectedCamera?.name}</h3>
                    <p>{selectedCamera?.location}</p>
                  </div>

                  <button className="secondary" onClick={() => setZoomCamera(selectedCamera)}>
                    Katta ko‘rish
                  </button>
                </div>

                <div className="big-camera-box">
                  <img src={selectedCamera?.streamUrl} alt={selectedCamera?.name} />
                </div>

                <div className="camera-info">
                  <span>ID: {selectedCamera?.id}</span>
                  <span>Status: {selectedCamera?.status}</span>
                  <span>Stream: active</span>
                </div>
              </div>
            </div>
          </section>
        )}

        {tab === "citizen" && (
          <div className="card">
            <div className="section-head">
              <div>
                <h3>Fuqarolardan kelgan xabarlar</h3>
                <p>Fuqarolar yuborgan xabarlar operator tomonidan tekshiriladi.</p>
              </div>
            </div>

            <div className="report-filters">
              <button
                className={reportFilter === "all" ? "active" : ""}
                onClick={() => setReportFilter("all")}
              >
                Hammasi
                <span>{reportCounts.all}</span>
              </button>

              <button
                className={reportFilter === "new" ? "active" : ""}
                onClick={() => setReportFilter("new")}
              >
                Yangi
                <span>{reportCounts.new}</span>
              </button>

              <button
                className={reportFilter === "reviewing" ? "active" : ""}
                onClick={() => setReportFilter("reviewing")}
              >
                Ko‘rib chiqilmoqda
                <span>{reportCounts.reviewing}</span>
              </button>

              <button
                className={reportFilter === "confirmed" ? "active" : ""}
                onClick={() => setReportFilter("confirmed")}
              >
                Tasdiqlandi
                <span>{reportCounts.confirmed}</span>
              </button>

              <button
                className={reportFilter === "rejected" ? "active" : ""}
                onClick={() => setReportFilter("rejected")}
              >
                Rad etildi
                <span>{reportCounts.rejected}</span>
              </button>
            </div>

            {filteredReports.length === 0 ? (
              <p className="muted">Bu filter bo‘yicha xabar yo‘q.</p>
            ) : (
              <div className="report-grid">
                {filteredReports.map((report) => (
                  <button
                    className="report-preview"
                    key={report.id}
                    onClick={() => setSelectedReport(report)}
                  >
                    <div className="item-top">
                      <strong>{report.location_text || "Joylashuv ko‘rsatilmagan"}</strong>
                      <span className={`status-badge ${statusClass(report.status)}`}>
                        {statusText(report.status)}
                      </span>
                    </div>

                    <p>{report.description}</p>

                    <small>
                      {report.reporter_type === "anonymous"
                        ? "Anonim"
                        : report.full_name || "Fuqaro"}{" "}
                      · {formatTime(report.created_at)}
                    </small>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "faceid" && (
          <div className="card">
            <div className="section-head">
              <div>
                <h3>Face ID baza</h3>
                <p>Ro‘yxatdan o‘tgan fuqarolar va operator qo‘shgan shaxslar.</p>
              </div>

              <button
                className="secondary"
                onClick={() => setShowFaceForm((prev) => !prev)}
              >
                {showFaceForm ? "Yopish" : "Odam qo‘shish"}
              </button>
            </div>

            <div className="report-filters">
              <button
                className={faceFilter === "all" ? "active" : ""}
                onClick={() => setFaceFilter("all")}
              >
                Hammasi
                <span>{faceRecords.length}</span>
              </button>

              <button
                className={faceFilter === "citizen" ? "active" : ""}
                onClick={() => setFaceFilter("citizen")}
              >
                Ro‘yxatdan o‘tganlar
                <span>{faceRecords.filter((item) => item.source === "citizen").length}</span>
              </button>

              <button
                className={faceFilter === "manual" ? "active" : ""}
                onClick={() => setFaceFilter("manual")}
              >
                Operator qo‘shganlar
                <span>{faceRecords.filter((item) => item.source === "manual").length}</span>
              </button>
            </div>

            {showFaceForm && (
              <form
                className="faceid-form"
                onSubmit={async (e) => {
                  e.preventDefault();

                  if (!newFace.face_image) {
                    alert("Yuz rasmi yuklang");
                    return;
                  }

                  await api.createFaceIdRecord({
                    full_name: newFace.full_name,
                    phone: newFace.phone || null,
                    risk_level: newFace.risk_level,
                    note: newFace.note || null,
                    source: "manual",
                    face_image: newFace.face_image,
                  });

                  setNewFace({
                    full_name: "",
                    phone: "",
                    risk_level: "unknown",
                    note: "",
                    face_image: "",
                  });

                  setShowFaceForm(false);
                  await loadData();
                }}
              >
                <div className="two-col">
                  <label>
                    Ism familiya
                    <input
                      value={newFace.full_name}
                      onChange={(e) =>
                        setNewFace((prev) => ({ ...prev, full_name: e.target.value }))
                      }
                      placeholder="Masalan: Ali Karimov"
                    />
                  </label>

                  <label>
                    Telefon
                    <input
                      value={newFace.phone}
                      onChange={(e) =>
                        setNewFace((prev) => ({ ...prev, phone: e.target.value }))
                      }
                      placeholder="+998..."
                    />
                  </label>
                </div>

                <div className="two-col">
                  <label>
                    Risk darajasi
                    <select
                      value={newFace.risk_level}
                      onChange={(e) =>
                        setNewFace((prev) => ({ ...prev, risk_level: e.target.value }))
                      }
                    >
                      <option value="unknown">Noma’lum</option>
                      <option value="low">Past</option>
                      <option value="medium">O‘rta</option>
                      <option value="high">Yuqori</option>
                    </select>
                  </label>

                  <label>
                    Yuz rasmi
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;

                        const reader = new FileReader();
                        reader.onload = () => {
                          setNewFace((prev) => ({
                            ...prev,
                            face_image: reader.result,
                          }));
                        };
                        reader.readAsDataURL(file);
                      }}
                    />
                  </label>
                </div>

                {newFace.face_image && (
                  <img className="faceid-preview" src={newFace.face_image} alt="preview" />
                )}

                <label>
                  Izoh
                  <textarea
                    value={newFace.note}
                    onChange={(e) =>
                      setNewFace((prev) => ({ ...prev, note: e.target.value }))
                    }
                    placeholder="Masalan: kuzatuv ro‘yxatiga qo‘shildi"
                  />
                </label>

                <button className="primary">Bazaga qo‘shish</button>
              </form>
            )}

            <div className="faceid-grid">
  {faceRecords
    .filter((item) => faceFilter === "all" || item.source === faceFilter)
    .map((record) => {
      const imageUrl = `${api.base}${record.face_image_url}`;

      return (
        <div className="faceid-card" key={record.id}>
          <button
            type="button"
            className="faceid-photo-button"
            onClick={() => setImageModal(imageUrl)}
          >
            <img src={imageUrl} alt={record.full_name} />
          </button>

          <div className="faceid-card-body">
            <div className="faceid-card-top">
              <div>
                <strong>{record.full_name}</strong>
                <p>{record.phone || "Telefon yo‘q"}</p>
              </div>

              <span
                className={
                  record.source === "citizen"
                    ? "face-source citizen"
                    : "face-source manual"
                }
              >
                {record.source === "citizen" ? "Fuqaro" : "Operator"}
              </span>
            </div>

            <div className="faceid-meta">
              <span>{record.id}</span>
              <span>{record.risk_level || "unknown"}</span>
            </div>

            <small>{record.note || "Izoh yo‘q"}</small>
          </div>
        </div>
      );
    })}
</div>
          </div>
        )}
        {tab === "faceMatch" && (
  <div className="card">
    <div className="section-head">
      <div>
        <h3>AI Face Matchmaking</h3>
        <p>
          Live camera orqali olingan yuz rasmi Face ID bazadagi rasmlar bilan
          solishtiriladi.
        </p>
      </div>

      <button className="secondary" onClick={loadLatestFaceMatch}>
        {faceMatchLoading ? "Tekshirilmoqda..." : "Oxirgi alertni tekshirish"}
      </button>
    </div>

    {!faceMatch || faceMatchLoading ? (
      <p className="muted">
        {faceMatchLoading
          ? "Face ID bazadan o‘xshashlik qidirilmoqda..."
          : "Hali face match bajarilmagan."}
      </p>
    ) : !faceMatch.ok ? (
      <div className="empty">
        <strong>Face match mavjud emas</strong>
        <p>{faceMatch.error || "Yuz rasmi bor alert hali mavjud emas."}</p>
      </div>
    ) : (
      <div className="face-match-layout">
        <div className="face-target-card">
          <span>Camera’dan olingan yuz</span>

          {faceMatch.target_face_image_url ? (
            <button
              type="button"
              className="face-target-photo"
              onClick={() =>
                setImageModal(`${api.base}${faceMatch.target_face_image_url}`)
              }
            >
              <img
                src={`${api.base}${faceMatch.target_face_image_url}`}
                alt="Target face"
              />
            </button>
          ) : (
            <div className="no-image">No face</div>
          )}

          <h4>{faceMatch.camera_name}</h4>
          <p>{formatTime(faceMatch.created_at)}</p>

          <div className="face-match-tags">
            <span>{faceMatch.event_type || "unknown_event"}</span>
            <span>{faceMatch.confidence}%</span>
          </div>
        </div>

        <div className="face-results">
          <div className="face-results-head">
            <div>
              <h4>Match natijalari</h4>
              <p>
                Engine: {faceMatch.result?.engine || "-"}
                {faceMatch.result?.facenet_error
                  ? ` · ${faceMatch.result.facenet_error}`
                  : ""}
              </p>
            </div>
          </div>

          {faceMatch.result?.best_match ? (
            <div className="best-match-card">
              <div className="best-match-label">Eng yaqin moslik</div>

              <div className="best-match-content">
                <button
                  type="button"
                  onClick={() =>
                    setImageModal(
                      `${api.base}${faceMatch.result.best_match.face_image_url}`
                    )
                  }
                >
                  <img
                    src={`${api.base}${faceMatch.result.best_match.face_image_url}`}
                    alt={faceMatch.result.best_match.full_name}
                  />
                </button>

                <div>
                  <h3>{faceMatch.result.best_match.full_name}</h3>
                  <p>{faceMatch.result.best_match.phone || "Telefon yo‘q"}</p>

                  <strong>{faceMatch.result.best_match.score}%</strong>
                  <span
                    className={`match-level ${faceMatch.result.best_match.match_level}`}
                  >
                    {faceMatch.result.best_match.match_label}
                  </span>

                  <small>
                    Source:{" "}
                    {faceMatch.result.best_match.source === "citizen"
                      ? "Ro‘yxatdan o‘tgan fuqaro"
                      : "Operator qo‘shgan baza"}
                  </small>
                </div>
              </div>
            </div>
          ) : (
            <p className="muted">Moslik topilmadi.</p>
          )}

          <div className="match-list">
            {(faceMatch.result?.matches || []).map((match) => (
              <div className="match-row" key={match.id}>
                <button
                  type="button"
                  onClick={() => setImageModal(`${api.base}${match.face_image_url}`)}
                >
                  <img src={`${api.base}${match.face_image_url}`} alt={match.full_name} />
                </button>

                <div>
                  <strong>{match.full_name}</strong>
                  <p>{match.phone || "Telefon yo‘q"}</p>
                  <small>{match.source} · {match.risk_level || "unknown"}</small>
                </div>

                <div className="match-score">
                  <b>{match.score}%</b>
                  <span className={`match-level ${match.match_level}`}>
                    {match.match_label}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )}
  </div>
)}

        {zoomCamera && (
          <div className="camera-modal">
            <div className="camera-modal-head">
              <div>
                <h2>{zoomCamera.name}</h2>
                <p>{zoomCamera.location}</p>
              </div>

              <button onClick={() => setZoomCamera(null)}>Yopish</button>
            </div>

            <div className="camera-modal-view">
              <img src={zoomCamera.streamUrl} alt={zoomCamera.name} />
            </div>
          </div>
        )}

        {selectedAlert && (
          <div className="detail-backdrop" onClick={() => setSelectedAlert(null)}>
            <aside className="detail-drawer" onClick={(e) => e.stopPropagation()}>
              <div className="drawer-head">
                <div>
                  <h2>AI alert tafsilotlari</h2>
                  <p>{selectedAlert.id}</p>
                </div>

                <button onClick={() => setSelectedAlert(null)}>Yopish</button>
              </div>

              {selectedAlert.evidence_image_url && (
                <img
                  className="drawer-image"
                  src={`${api.base}${selectedAlert.evidence_image_url}`}
                  alt="evidence"
                  onClick={() => setImageModal(`${api.base}${selectedAlert.evidence_image_url}`)}
                />
              )}
              {selectedAlert.evidence_video_url && (
  <div className="drawer-section">
    <span>Incident video</span>
    <video
      className="incident-video"
      src={`${api.base}${selectedAlert.evidence_video_url}`}
      controls
      playsInline
    />
  </div>
)}
              {selectedAlert.evidence_gallery_urls?.length > 0 && (
  <div className="drawer-section">
    <span>Evidence gallery</span>

    <div className="evidence-gallery">
      {selectedAlert.evidence_gallery_urls.map((url, index) => {
        const imageUrl = `${api.base}${url}`;

        return (
          <button
            type="button"
            key={`${url}-${index}`}
            onClick={() => setImageModal(imageUrl)}
          >
            <img src={imageUrl} alt={`Evidence frame ${index + 1}`} />
            <small>Frame {index + 1}</small>
          </button>
        );
      })}
    </div>
  </div>
)}

              <div className="detail-grid">
                <div>
                  <span>Kamera</span>
                  <strong>{selectedAlert.camera_name}</strong>
                </div>

                <div>
                  <span>Confidence</span>
                  <strong>{selectedAlert.confidence}%</strong>
                </div>

                <div>
                  <span>Shaxs ID</span>
                  <strong>{selectedAlert.person_id}</strong>
                </div>

                <div>
                  <span>FaceID</span>
                  <strong>
                    {selectedAlert.face_match_name} · {selectedAlert.face_match_score}%
                  </strong>
                </div>

                <div>
                  <span>Joylashuv</span>
                  <strong>
                    {selectedAlert.latitude}, {selectedAlert.longitude}
                  </strong>
                </div>

                <div>
                  <span>Vaqt</span>
                  <strong>{formatTime(selectedAlert.created_at)}</strong>
                </div>

                <div>
                  <span>Status</span>
                  <strong className={`status-badge ${statusClass(selectedAlert.status)}`}>
                    {statusText(selectedAlert.status)}
                  </strong>
                </div>

                <div>
                  <span>Ko‘rib chiqqan operator</span>
                  <strong>{selectedAlert.reviewed_by || "-"}</strong>
                </div>

                <div>
                  <span>Review vaqti</span>
                  <strong>{formatTime(selectedAlert.reviewed_at)}</strong>
                </div>
              </div>

              <div className="drawer-section">
                <span>Aniqlangan harakat</span>
                <p>{selectedAlert.action}</p>
              </div>

              <div className="drawer-section">
                <span>Operator izohi</span>
                <p>{selectedAlert.review_note || "Hali izoh yozilmagan"}</p>
              </div>

              <div className="actions">
              {selectedAlert.face_image_url && (
  <button onClick={() => loadFaceMatchForAlert(selectedAlert.id)}>
    Face Match
  </button>
)}
                <button onClick={() => openReviewModal("alert", selectedAlert, "tasdiqlandi")}>
                  Tasdiqlash
                </button>

                <button onClick={() => openReviewModal("alert", selectedAlert, "rad_etildi")}>
                  Rad etish
                </button>
              </div>
            </aside>
          </div>
        )}

        {selectedReport && (
          <div className="detail-backdrop" onClick={() => setSelectedReport(null)}>
            <aside className="detail-drawer" onClick={(e) => e.stopPropagation()}>
              <div className="drawer-head">
                <div>
                  <h2>Fuqaro xabari tafsilotlari</h2>
                  <p>{selectedReport.id}</p>
                </div>

                <button onClick={() => setSelectedReport(null)}>Yopish</button>
              </div>

              {selectedReport.evidence_image_url && (
                <img
                  className="drawer-image"
                  src={`${api.base}${selectedReport.evidence_image_url}`}
                  alt="Citizen evidence"
                  onClick={() => setImageModal(`${api.base}${selectedReport.evidence_image_url}`)}
                />
              )}

              <div className="detail-grid">
                <div>
                  <span>Yuboruvchi</span>
                  <strong>
                    {selectedReport.reporter_type === "anonymous"
                      ? "Anonim"
                      : selectedReport.full_name || "Fuqaro"}
                  </strong>
                </div>

                <div>
                  <span>Telefon</span>
                  <strong>{selectedReport.phone || "-"}</strong>
                </div>

                <div>
                  <span>Joylashuv</span>
                  <strong>{selectedReport.location_text || "-"}</strong>
                </div>

                <div>
                  <span>Koordinata</span>
                  <strong>
                    {selectedReport.latitude && selectedReport.longitude
                      ? `${selectedReport.latitude}, ${selectedReport.longitude}`
                      : "-"}
                  </strong>
                </div>

                <div>
                  <span>Vaqt</span>
                  <strong>{formatTime(selectedReport.created_at)}</strong>
                </div>

                <div>
                  <span>Status</span>
                  <strong className={`status-badge ${statusClass(selectedReport.status)}`}>
                    {statusText(selectedReport.status)}
                  </strong>
                </div>

                <div>
                  <span>Ko‘rib chiqqan operator</span>
                  <strong>{selectedReport.reviewed_by || "-"}</strong>
                </div>

                <div>
                  <span>Review vaqti</span>
                  <strong>{formatTime(selectedReport.reviewed_at)}</strong>
                </div>
              </div>

              <div className="drawer-section">
                <span>Xabar matni</span>
                <p>{selectedReport.description}</p>
              </div>

              <div className="drawer-section">
                <span>Dalil izohi</span>
                <p>{selectedReport.evidence_note || "-"}</p>
              </div>

              <div className="drawer-section">
                <span>Operator izohi</span>
                <p>{selectedReport.review_note || "Hali izoh yozilmagan"}</p>
              </div>

              <div className="actions">
                <button onClick={() => openReviewModal("report", selectedReport, "reviewing")}>
                  Ko‘rib chiqish
                </button>

                <button onClick={() => openReviewModal("report", selectedReport, "confirmed")}>
                  Tasdiqlash
                </button>

                <button onClick={() => openReviewModal("report", selectedReport, "rejected")}>
                  Rad etish
                </button>
              </div>
            </aside>
          </div>
        )}

        {imageModal && (
          <div className="image-modal" onClick={() => setImageModal(null)}>
            <button onClick={() => setImageModal(null)}>Yopish</button>
            <img src={imageModal} alt="large evidence" />
          </div>
        )}

        {reviewModal && (
          <div className="review-backdrop" onClick={() => setReviewModal(null)}>
            <form
              className="review-box"
              onSubmit={(e) => e.preventDefault()}
              onClick={(e) => e.stopPropagation()}
            >
              <h2>Operator qarori</h2>
              <p>{reviewModal.title}</p>

              <div className="review-status">
                Qaror:{" "}
                <b className={`status-badge ${statusClass(reviewModal.status)}`}>
                  {statusText(reviewModal.status)}
                </b>
              </div>

              <label>
                Operator izohi
                <textarea
                  value={reviewNote}
                  onChange={(e) => setReviewNote(e.target.value)}
                  placeholder="Masalan: video evidence tekshirildi, holat tasdiqlandi..."
                />
              </label>

              <div className="review-actions">
                <button type="button" className="secondary" onClick={() => setReviewModal(null)}>
                  Bekor qilish
                </button>

                <button type="button" className="primary" onClick={submitReview}>
                  Saqlash
                </button>
              </div>
            </form>
          </div>
        )}
      </main>
    </div>
  );
}

export default OperatorDashboard;