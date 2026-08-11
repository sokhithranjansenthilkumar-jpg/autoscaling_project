import React from "react";
import PredictForm from "./components/PredictForm";

function App() {
  return (
    <div className="app-root">
      <div className="bg-layer" />
      <main className="app-shell">
        <header className="hero">
          <p className="kicker">Adaptive Cloud Intelligence</p>
          <h1>Autoscaling Executive Dashboard</h1>
          <p>
            A cleaner control room for prediction, live marketplace updates,
            and infrastructure health. Built for your autoscaling workflow
            instead of a generic model demo.
          </p>
        </header>
        <PredictForm />
      </main>
    </div>
  );
}

export default App;
