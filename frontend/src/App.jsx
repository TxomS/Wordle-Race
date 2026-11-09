import { useEffect, useState } from "react";

// Placeholder for the first milestone: proves the whole path
// browser -> nginx -> backend works before any game code exists.
export default function App() {
  const [backend, setBackend] = useState("checking...");

  useEffect(() => {
    fetch("/api/health")
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then((data) => setBackend(data.status === "ok" ? "OK" : "unexpected reply"))
      .catch(() => setBackend("unreachable"));
  }, []);

  return (
    <main className="page">
      <h1>Wordle Race</h1>
      <p>
        Backend: <strong>{backend}</strong>
      </p>
    </main>
  );
}
