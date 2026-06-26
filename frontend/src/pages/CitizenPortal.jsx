import { useState } from "react";
import { api } from "../api";

function CitizenPortal({ onBack }) {
  const [type, setType] = useState("anonymous");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [description, setDescription] = useState("");
  const [locationText, setLocationText] = useState("");
  const [evidenceNote, setEvidenceNote] = useState("");
  const [success, setSuccess] = useState(null);
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setLoading(true);

    try {
      const payload = {
        reporter_type: type,
        full_name: type === "identified" ? fullName : null,
        phone: type === "identified" ? phone : null,
        description,
        location_text: locationText || null,
        latitude: null,
        longitude: null,
        evidence_note: evidenceNote || null,
      };

      const data = await api.createCitizenReport(payload);
      setSuccess(data.report);

      setType("anonymous");
      setFullName("");
      setPhone("");
      setDescription("");
      setLocationText("");
      setEvidenceNote("");
    } catch (err) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="simple-page">
        <div className="card form-card center">
          <h2>Xabaringiz yuborildi</h2>
          <p>Operatorlar uni ko‘rib chiqadi.</p>
          <p>
            Xabar ID: <b>{success.id}</b>
          </p>

          <button className="primary" onClick={() => setSuccess(null)}>
            Yana xabar yuborish
          </button>

          <button className="secondary" onClick={onBack}>
            Bosh sahifa
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="simple-page">
      <form className="card form-card wide" onSubmit={submit}>
        <button type="button" className="link-button" onClick={onBack}>
          ← Bosh sahifa
        </button>

        <h2>Fuqaro xabari</h2>
        <p>Shubhali holat haqida operatorlarga xabar yuboring.</p>

        <div className="toggle">
          <button
            type="button"
            className={type === "anonymous" ? "active" : ""}
            onClick={() => setType("anonymous")}
          >
            Anonim
          </button>

          <button
            type="button"
            className={type === "identified" ? "active" : ""}
            onClick={() => setType("identified")}
          >
            Ism bilan
          </button>
        </div>

        {type === "identified" && (
          <div className="two-col">
            <label>
              Ism familiya
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </label>

            <label>
              Telefon
              <input value={phone} onChange={(e) => setPhone(e.target.value)} />
            </label>
          </div>
        )}

        <label>
          Xabar matni
          <textarea
            required
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Nima ko‘rdingiz? Qayerda? Qachon?"
          />
        </label>

        <label>
          Joylashuv
          <input
            value={locationText}
            onChange={(e) => setLocationText(e.target.value)}
            placeholder="Masalan: Guliston park, kirish joyi yonida"
          />
        </label>

        <label>
          Qo‘shimcha dalil izohi
          <textarea
            value={evidenceNote}
            onChange={(e) => setEvidenceNote(e.target.value)}
            placeholder="Masalan: rasm/video bor, kerak bo‘lsa taqdim qilaman"
          />
        </label>

        <button className="primary" disabled={loading}>
          {loading ? "Yuborilmoqda..." : "Xabar yuborish"}
        </button>
      </form>
    </div>
  );
}

export default CitizenPortal;