import { useCallback, useEffect, useRef, useState } from "react";
import { createGame, joinGame } from "../api.js";
import Board from "../components/Board.jsx";
import Keyboard from "../components/Keyboard.jsx";
import Lobby from "../components/Lobby.jsx";
import OpponentPanel from "../components/OpponentPanel.jsx";
import { useGame } from "../hooks/useGame.js";
import { keyboardState } from "../keyboardState.js";
import { isConnectionProblem, messageFor } from "../messages.js";
import { saveToken } from "../session.js";

function resultTitle(result, mode) {
  switch (result.reason) {
    case "solved":
      return mode === "race" ? "You solved it first!" : "You got it!";
    case "opponent_solved":
      return "Your opponent solved it first.";
    case "out_of_guesses":
      return "Out of guesses.";
    default:
      return "Nobody solved it.";
  }
}

function Notice({ title, children, actions, navigate }) {
  return (
    <section className="notice">
      <h1>{title}</h1>
      {children}
      <div className="actions">
        {actions}
        <button type="button" className="button" onClick={() => navigate("/")}>
          Home
        </button>
      </div>
    </section>
  );
}

export default function Game({ code, navigate }) {
  const { phase, game, error, reconnecting, submit, retry } = useGame(code);
  const [typed, setTyped] = useState("");
  const [toast, setToast] = useState(null);
  const [shake, setShake] = useState(false);
  const [busy, setBusy] = useState(false);
  const [joinError, setJoinError] = useState(null);

  const wordLength = game?.word_length ?? 5;
  const canType = phase === "ready" && game.status === "playing" && game.me.status === "playing" && !busy;

  const showToast = useCallback((text) => setToast({ text, id: Date.now() }), []);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = setTimeout(() => setToast(null), 1800);
    return () => clearTimeout(timer);
  }, [toast]);

  // Tell the creator the moment the opponent arrives.
  const previousStatus = useRef(null);
  useEffect(() => {
    const status = game?.status ?? null;
    if (previousStatus.current === "waiting" && status === "playing") showToast("Opponent joined. Go!");
    previousStatus.current = status;
  }, [game?.status, showToast]);

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

  // Someone opened a game link in a tab that has no seat in it: offer to take the free one.
  async function joinThisGame() {
    setBusy(true);
    setJoinError(null);
    try {
      const session = await joinGame(code);
      saveToken(session.code, session.token);
      setBusy(false);
      retry(); // load the game again, now with a token
    } catch (problem) {
      setJoinError(messageFor(problem));
      setBusy(false);
    }
  }

  if (phase === "loading") return <p className="status">Loading game...</p>;
  if (phase === "not-found") {
    return (
      <Notice title="Game not found" navigate={navigate}>
        <p>There is no game with the code {code}.</p>
      </Notice>
    );
  }
  if (phase === "no-access") {
    return (
      <Notice
        title={`Join game ${code}?`}
        navigate={navigate}
        actions={
          <button type="button" className="button button--primary" onClick={joinThisGame} disabled={busy}>
            {busy ? "Joining..." : "Join this game"}
          </button>
        }
      >
        <p>This browser tab is not part of the game yet.</p>
        {joinError && (
          <p className="error" role="alert">
            {joinError}
          </p>
        )}
      </Notice>
    );
  }
  if (phase === "error") {
    return (
      <Notice
        title="Connection problem"
        navigate={navigate}
        actions={
          <button type="button" className="button button--primary" onClick={retry}>
            Try again
          </button>
        }
      >
        <p>{isConnectionProblem(error) ? "Cannot reach the server." : messageFor(error)}</p>
      </Notice>
    );
  }

  const result = game.result;
  const race = game.mode === "race";
  const waiting = game.status === "waiting";

  return (
    <div className="game">
      <div className="toast-region" aria-live="polite">
        {toast && (
          <div className="toast" key={toast.id}>
            {toast.text}
          </div>
        )}
      </div>

      {reconnecting && (
        <p className="banner" role="status">
          Reconnecting...
        </p>
      )}

      {waiting ? (
        <Lobby code={code} />
      ) : (
        <>
          <div className="boards">
            <Board
              label="Your board"
              guesses={game.me.guesses}
              typed={game.status === "playing" ? typed : ""}
              maxGuesses={game.max_guesses}
              wordLength={wordLength}
              shake={shake}
            />
            {race && game.opponent && (
              <OpponentPanel opponent={game.opponent} maxGuesses={game.max_guesses} wordLength={wordLength} />
            )}
          </div>

          {race && !result && game.me.status === "out_of_guesses" && (
            <p className="note" role="status">
              You are out of guesses. Waiting for your opponent...
            </p>
          )}

          {result && (
            <section className={`result result--${result.outcome}`} role="status">
              <h2>{resultTitle(result, game.mode)}</h2>
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
        </>
      )}
    </div>
  );
}
