import { useCallback, useEffect, useState } from "react";
import { createGame } from "../api.js";
import Board from "../components/Board.jsx";
import Keyboard from "../components/Keyboard.jsx";
import { useGame } from "../hooks/useGame.js";
import { keyboardState } from "../keyboardState.js";
import { isConnectionProblem, messageFor } from "../messages.js";
import { saveToken } from "../session.js";

const RESULT_TITLE = {
  solved: "You got it!",
  opponent_solved: "Your opponent solved it first.",
  out_of_guesses: "Out of guesses.",
  both_out_of_guesses: "Nobody solved it.",
};

function Notice({ title, children, retry, navigate }) {
  return (
    <section className="notice">
      <h1>{title}</h1>
      <p>{children}</p>
      <div className="actions">
        {retry && (
          <button type="button" className="button button--primary" onClick={retry}>
            Try again
          </button>
        )}
        <button type="button" className="button" onClick={() => navigate("/")}>
          Home
        </button>
      </div>
    </section>
  );
}

export default function Game({ code, navigate }) {
  const { phase, game, error, submit, retry } = useGame(code);
  const [typed, setTyped] = useState("");
  const [toast, setToast] = useState(null);
  const [shake, setShake] = useState(false);
  const [busy, setBusy] = useState(false);

  const wordLength = game?.word_length ?? 5;
  const canType = phase === "ready" && game.status === "playing" && game.me.status === "playing" && !busy;

  const showToast = useCallback((text) => setToast({ text, id: Date.now() }), []);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = setTimeout(() => setToast(null), 1800);
    return () => clearTimeout(timer);
  }, [toast]);

  const rejectRow = useCallback(
    (text) => {
      showToast(text);
      setShake(true);
      setTimeout(() => setShake(false), 500);
    },
    [showToast],
  );

  // One entry point for both keyboards: a letter, "Enter" or "Backspace".
  const handleKey = useCallback(
    async (key) => {
      if (!canType) return;
      if (key === "Backspace") {
        setTyped((current) => current.slice(0, -1));
      } else if (key === "Enter") {
        if (typed.length < wordLength) {
          rejectRow("Not enough letters");
          return;
        }
        setBusy(true);
        const result = await submit(typed);
        setBusy(false);
        if (result.ok) setTyped("");
        else rejectRow(messageFor(result.error)); // keep the letters so they can be fixed
      } else if (/^[a-z]$/.test(key)) {
        setTyped((current) => (current.length < wordLength ? current + key : current));
      }
    },
    [canType, typed, wordLength, submit, rejectRow],
  );

  useEffect(() => {
    function onKeyDown(event) {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      // Enter on a focused button (Play again, Home...) belongs to that button.
      if (event.key === "Enter" && event.target.closest?.("button, a")) return;
      const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
      if (key === "Enter" || key === "Backspace" || /^[a-z]$/.test(key)) {
        event.preventDefault();
        handleKey(key);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleKey]);

  async function playAgain() {
    if (game.mode !== "solo") {
      navigate("/");
      return;
    }
    setBusy(true);
    try {
      const session = await createGame("solo");
      saveToken(session.code, session.token);
      navigate(`/g/${session.code}`);
    } catch (problem) {
      showToast(messageFor(problem));
      setBusy(false);
    }
  }

  if (phase === "loading") return <p className="status">Loading game...</p>;
  if (phase === "not-found") {
    return (
      <Notice title="Game not found" navigate={navigate}>
        There is no game with the code {code}.
      </Notice>
    );
  }
  if (phase === "no-access") {
    return (
      <Notice title="This game is open somewhere else" navigate={navigate}>
        A game can only be played in the browser tab where it was started.
      </Notice>
    );
  }
  if (phase === "error") {
    return (
      <Notice title="Connection problem" retry={retry} navigate={navigate}>
        {isConnectionProblem(error) ? "Cannot reach the server." : messageFor(error)}
      </Notice>
    );
  }

  const result = game.result;
  return (
    <div className="game">
      <div className="toast-region" aria-live="polite">
        {toast && (
          <div className="toast" key={toast.id}>
            {toast.text}
          </div>
        )}
      </div>

      <Board
        label="Your board"
        guesses={game.me.guesses}
        typed={game.status === "playing" ? typed : ""}
        maxGuesses={game.max_guesses}
        wordLength={wordLength}
        shake={shake}
      />

      {result && (
        <section className={`result result--${result.outcome}`} role="status">
          <h2>{RESULT_TITLE[result.reason]}</h2>
          <p>
            The word was <strong>{result.answer.toUpperCase()}</strong>.
          </p>
          <div className="actions">
            <button type="button" className="button button--primary" onClick={playAgain} disabled={busy}>
              {game.mode === "solo" ? "Play again" : "Back to start"}
            </button>
            {game.mode === "solo" && (
              <button type="button" className="button" onClick={() => navigate("/")}>
                Home
              </button>
            )}
          </div>
        </section>
      )}

      {!result && <Keyboard state={keyboardState(game.me.guesses)} onKey={handleKey} disabled={!canType} />}
    </div>
  );
}
