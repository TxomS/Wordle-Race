import { useState } from "react";
import { createGame } from "../api.js";
import { messageFor } from "../messages.js";
import { saveToken } from "../session.js";

export default function Home({ navigate }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function playSolo() {
    setBusy(true);
    setError(null);
    try {
      const session = await createGame("solo");
      saveToken(session.code, session.token);
      navigate(`/g/${session.code}`);
    } catch (problem) {
      setError(messageFor(problem));
      setBusy(false);
    }
  }

  return (
    <section className="home">
      <h1>Guess the word</h1>
      <p className="lead">Find the hidden 5-letter word in 6 tries.</p>

      <ul className="legend">
        <li>
          <span className="swatch swatch--green">W</span> Right letter, right place
        </li>
        <li>
          <span className="swatch swatch--yellow">W</span> In the word, but somewhere else
        </li>
        <li>
          <span className="swatch swatch--grey">W</span> Not in the word
        </li>
      </ul>

      <button type="button" className="button button--primary" onClick={playSolo} disabled={busy}>
        {busy ? "Starting..." : "Play solo"}
      </button>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
