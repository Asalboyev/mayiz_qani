import { useState } from "react";
import { api } from "../api";

function OperatorLogin({ onBack, onLogin }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("safedrop123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await api.loginOperator(username, password);
      onLogin();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="simple-page">
      <form className="card form-card" onSubmit={submit}>
        <button type="button" className="link-button" onClick={onBack}>
          ← Orqaga
        </button>

        <h2>Operator login</h2>
        <p>Cybersecurity xodimlari uchun kirish.</p>

        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} />
        </label>

        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>

        {error && <div className="error">{error}</div>}

        <button className="primary" disabled={loading}>
          {loading ? "Tekshirilmoqda..." : "Kirish"}
        </button>

        <small>Demo: admin / safedrop123</small>
      </form>
    </div>
  );
}

export default OperatorLogin;