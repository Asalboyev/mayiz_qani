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
    const saved = localStorage.getItem("safedrop_cameras");
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
  const [auditLogs, setAuditLogs] = useState([]);

  const [cameras, setCameras] = useState(loadSavedCameras);
  const [selectedCameraId, setSelectedCameraId] = useState("CAM-01");
  const [showCameraForm, setShowCameraForm] = useState(false);
  const [zoomCamera, setZoomCamera] = useState(null);

  const [selectedAlert, setSelectedAlert] = useState(null);
  const [selectedReport, setSelectedReport] = useState(null);
  const [imageModal, setImageModal] = useState(null);

  const [reviewModal, setReviewModal] = useState(null);
  const [reviewNote, setReviewNote] = useState("");

  const [newCamera, setNewCamera] = useState({
    name: "",
    location: "",
    streamUrl: "",
  });

  const selectedCamera = useMemo(() => {
    return cameras.find((camera) => camera.id === selectedCameraId) || cameras[0];
  }, [cameras, selectedCameraId]);

  async function loadData() {
    try {
      const [healthData, alertData, reportData, auditData] = await Promise.all([
        api.health(),
        api.getAlerts(),
        api.getCitizenReports(),
        api.getAuditLogs(),
      ]);

      setHealth(healthData);
      setAlerts(alertData.alerts || []);
      setReports(reportData.reports || []);
      setAuditLogs(auditData.logs || []);

      if (selectedAlert) {
        const freshAlert = (alertData.alerts || []).find((item) => item.id === selectedAlert.id);
        if (freshAlert) setSelectedAlert(freshAlert);
      }

      if (selectedReport) {
        const freshReport = (reportData.reports || []).find((item) => item.id === selectedReport.id);
        if (freshReport) setSelectedReport(freshReport);
      }
    } catch (err) {
      console.error(err);
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
    localStorage.setItem("safedrop_cameras", JSON.stringify(cameras));
  }, [cameras]);

  return (
    <div className="dashboard">
      <aside className="dash-sidebar">
        <h2>SafeDrop AI</h2>
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
          className={tab === "audit" ? "active" : ""}
          onClick={() => setTab("audit")}
        >
          Audit logs
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
                        <span>{statusText(alert.status)}</span>
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

            {reports.length === 0 ? (
              <p className="muted">Hozircha xabar yo‘q.</p>
            ) : (
              <div className="report-grid">
                {reports.map((report) => (
                  <button
                    className="report-preview"
                    key={report.id}
                    onClick={() => setSelectedReport(report)}
                  >
                    <div className="item-top">
                      <strong>{report.location_text || "Joylashuv ko‘rsatilmagan"}</strong>
                      <span>{statusText(report.status)}</span>
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

        {tab === "audit" && (
          <div className="card">
            <h3>Audit logs</h3>
            <p className="muted">Operatorlar qilgan tasdiqlash/rad etish ishlari.</p>

            {auditLogs.length === 0 ? (
              <p className="muted">Hozircha audit log yo‘q.</p>
            ) : (
              <div className="list">
                {auditLogs.map((log) => (
                  <div className="item" key={log.id}>
                    <div className="item-top">
                      <strong>{log.entity_type}</strong>
                      <span>{log.action}</span>
                    </div>

                    <p>{log.note || "Izoh yo‘q"}</p>
                    <small>
                      Operator: {log.operator} · {formatTime(log.created_at)}
                    </small>
                  </div>
                ))}
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
                  <strong>{statusText(selectedAlert.status)}</strong>
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
                  <strong>{statusText(selectedReport.status)}</strong>
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
            <form className="review-box" onSubmit={(e) => e.preventDefault()} onClick={(e) => e.stopPropagation()}>
              <h2>Operator qarori</h2>
              <p>{reviewModal.title}</p>

              <div className="review-status">
                Qaror: <b>{statusText(reviewModal.status)}</b>
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