import { useEffect, useState } from "react";
import "./App.css";

import Landing from "./pages/Landing";
import CitizenPortal from "./pages/CitizenPortal";
import OperatorLogin from "./pages/OperatorLogin";
import OperatorDashboard from "./pages/OperatorDashboard";

function App() {
  const [page, setPage] = useState("landing");
  const [citizen, setCitizen] = useState(() => {
    const saved = localStorage.getItem("safedrop_citizen");
    return saved ? JSON.parse(saved) : null;
  });

  const [theme, setTheme] = useState(() => {
  return localStorage.getItem("safedrop_theme") || "light";
});
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("safedrop_theme", theme);
  }, [theme]);

  function toggleTheme() {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  }

  function handleCitizenLogin(user) {
    setCitizen(user);
    setPage("citizen");
  }

  function citizenLogout() {
    setCitizen(null);
    setPage("landing");
  }

  function renderPage() {
    if (page === "citizen") {
      return <CitizenPortal citizen={citizen} onLogout={citizenLogout} />;
    }

    if (page === "operator-login") {
      return (
        <OperatorLogin
          onBack={() => setPage("landing")}
          onLogin={() => setPage("operator")}
        />
      );
    }

    if (page === "operator") {
      return <OperatorDashboard onLogout={() => setPage("landing")} />;
    }

    return (
      <Landing
        onCitizenLogin={handleCitizenLogin}
        onOperator={() => setPage("operator-login")}
      />
    );
  }

  return (
    <>
      <button className="theme-toggle" onClick={toggleTheme}>
        {theme === "light" ? "🌙 Dark" : "☀️ Light"}
      </button>

      {renderPage()}
    </>
  );
}

export default App;