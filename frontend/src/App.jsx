import { useState } from "react";
import "./App.css";

import Landing from "./pages/Landing";
import CitizenPortal from "./pages/CitizenPortal";
import OperatorLogin from "./pages/OperatorLogin";
import OperatorDashboard from "./pages/OperatorDashboard";

function App() {
  const [page, setPage] = useState("landing");

  if (page === "citizen") {
    return <CitizenPortal onBack={() => setPage("landing")} />;
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
      onCitizen={() => setPage("citizen")}
      onOperator={() => setPage("operator-login")}
    />
  );
}

export default App;