import { useState } from "react";
import { api } from "../api";

function CitizenPortal({ citizen, onLogout }) {
  const [description, setDescription] = useState("");
  const [locationText, setLocationText] = useState("");
  const [evidenceNote, setEvidenceNote] = useState("");
  const [evidenceFile, setEvidenceFile] = useState(null);
  const [success, setSuccess] = useState(null);
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setLoading(true);

    try {
      const formData = new FormData();

      formData.append("reporter_type", "identified");
      formData.append("full_name", citizen.full_name);
      formData.append("phone", citizen.phone);
      formData.append("description", description);
      formData.append("location_text", locationText);
      formData.append("evidence_note", evidenceNote);
      formData.append("latitude", "");
      formData.append("longitude", "");

      if (evidenceFile) {
        formData.append("evidence_file", evidenceFile);
      }

      const data = await api.createCitizenReportWithEvidence(formData);
      setSuccess(data.report);

      setDescription("");
      setLocationText("");
      setEvidenceNote("");
      setEvidenceFile(null);
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

          <button className="secondary" onClick={onLogout}>
            Chiqish
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="simple-page">
      <form className="card form-card wide" onSubmit={submit}>
        <div className="citizen-profile">
          <img src={citizen.face_image} alt="FaceID" />

          <div>
            <h2>{citizen.full_name}</h2>
            <p>{citizen.phone}</p>
            <span>{citizen.face_id}</span>
          </div>

          <button type="button" className="secondary" onClick={onLogout}>
            Chiqish
          </button>
        </div>

        <h2>Shubhali holat haqida xabar yuborish</h2>
        <p>Rasm yuklasangiz operator panelida evidence sifatida ko‘rinadi.</p>

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
          Shubhali holat rasmi
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setEvidenceFile(e.target.files?.[0] || null)}
          />
        </label>

        <label>
          Qo‘shimcha izoh
          <textarea
            value={evidenceNote}
            onChange={(e) => setEvidenceNote(e.target.value)}
            placeholder="Masalan: rasmda devor yonidagi joy ko‘rinadi"
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