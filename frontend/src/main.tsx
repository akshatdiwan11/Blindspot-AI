import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";

function App() {
  return <div className="p-10 font-display text-4xl">Blindspot AI</div>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
