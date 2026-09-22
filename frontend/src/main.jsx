import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import { UnitProvider } from "./UnitContext.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <UnitProvider>
      <App />
    </UnitProvider>
  </React.StrictMode>
);
