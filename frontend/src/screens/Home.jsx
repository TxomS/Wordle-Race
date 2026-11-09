import { useState } from "react";
import { createGame, joinGame } from "../api.js";
import { messageFor } from "../messages.js";
import { loadToken, saveToken } from "../session.js";

// Only the shape is checked here (5 letters or digits). Whether the game exists, and
// whether it has room, is the server's decision.
const CODE_PATTERN = /^[A-Z0-9]{5}$/;

export default function Home({ navigate }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [code, setCode] = useState("");

  async function start(mode) {
    setBusy(true);
    setError(null);
    try {
      const session = await createGame(mode);
      saveToken(session.code, session.token);
      navigate(`/g/${session.code}`);
    } catch (problem) {
      setError(messageFor(problem));
      setBusy(false);
    }
  }

  async function join(event) {
    event.preventDefault();
    const clean = code.trim().toUpperCase();
    if (!CODE_PATTERN.test(clean)) {
      setError("Enter the 5-character game code");
      return;
    }
    if (loadToken(clean)) {
      navigate(`/g/${clean}`); // this tab already has a seat in that game: just open it
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const session = await joinGame(clean);
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

      <div className="actions">
        <button type="button" className="button button--primary" onClick={() => start("solo")} disabled={busy}>
          Play Solo
        </button>
        <button type="button" className="button" onClick={() => start("race")} disabled={busy}>
          Play Co-op
        </button>
      </div>

      <form className="join" onSubmit={join}>
        <label htmlFor="join-code">Have a code? Join a friend's race</label>
        <div className="join__row">
          <input
            id="join-code"
            className="join__input"
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            maxLength={5}
            placeholder="ABCDE"
            autoCapitalize="characters"
            autoComplete="off"
            spellCheck={false}
          />
          <button type="submit" className="button button--join" disabled={busy}>
            Join
          </button>
        </div>
      </form>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
