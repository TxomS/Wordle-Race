import { useCallback, useEffect, useRef, useState } from "react";
import { getGame, submitGuess } from "../api.js";
import { forgetToken, loadToken } from "../session.js";

// How often a race asks the server what the opponent is doing. Wordle turns take
// seconds, so a delay of at most 1.5 s is invisible. A hidden tab asks less often.
const POLL_MS = 1500;
const POLL_HIDDEN_MS = 5000;
const POLL_MAX_BACKOFF_MS = 10000;

// A solo game has no opponent to wait for, but the page still asks the server every 30 s.
// That tells the server the page is open, so the game is not deleted while the player is
// away thinking. (The server deletes a game only when nobody has touched it AND nobody has
// asked about it for 15 minutes.)
const HEARTBEAT_MS = 30000;

// Everything about one game that the screen needs: loading it, keeping it fresh
// (in a race), and sending guesses.
//
// phase:
//   "loading"    waiting for the server
//   "ready"      `game` holds the latest view from the server
//   "no-access"  this tab has no valid token for the game
//   "not-found"  no game with this code
//   "lobby-expired"  the lobby we were waiting in has been closed by the server
//   "error"      the server could not be reached on the first load; `error` says why
//
// `reconnecting` is true while polling cannot reach the server. The last known game
// stays on screen, and polling resumes by itself when the server is back.
//
// The server is the authority: the screen never changes the board by itself, it only
// shows the `game` the server last sent.
export function useGame(code) {
  const [state, setState] = useState({ phase: "loading", game: null, error: null });
  const [reconnecting, setReconnecting] = useState(false);
  const [attempt, setAttempt] = useState(0); // bumped by retry() to load again
  const tokenRef = useRef(null);
  const gameRef = useRef(null);
  const changes = useRef(0); // counts guesses sent or applied; see the polling note below
  gameRef.current = state.game;

  // Load the game once.
  useEffect(() => {
    let cancelled = false;
    const token = loadToken(code);
    tokenRef.current = token;
    setReconnecting(false);

    if (!token) {
      setState({ phase: "no-access", game: null, error: null });
      return undefined;
    }

    setState((current) => ({ ...current, phase: "loading" }));
    getGame(code, token)
      .then((game) => {
        if (!cancelled) setState({ phase: "ready", game, error: null });
      })
      .catch((error) => {
        if (cancelled) return;
        if (error.code === "NOT_FOUND") {
          setState({ phase: "not-found", game: null, error });
        } else if (error.status === 401) {
          forgetToken(code); // the server does not know this token any more
          setState({ phase: "no-access", game: null, error });
        } else {
          setState({ phase: "error", game: null, error });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [code, attempt]);

  // Ask the server again and again until the game is finished: quickly in a race, to see
  // the opponent's moves; slowly in a solo game, only to show the page is still open.
  const mode = state.game?.mode;
  const polling = state.phase === "ready" && state.game.status !== "finished";
  useEffect(() => {
    if (!polling) return undefined;
    let cancelled = false;
    let timer;
    let failures = 0;

    async function poll() {
      const changesBefore = changes.current;
      try {
        const game = await getGame(code, tokenRef.current);
        if (cancelled) return;
        failures = 0;
        setReconnecting(false);
        // If we sent a guess while this request was travelling, its answer may be older
        // than what we already know. Throw it away; the next poll will be current.
        if (changes.current === changesBefore) setState({ phase: "ready", game, error: null });
      } catch (error) {
        if (cancelled) return;
        if (error.code === "NOT_FOUND") {
          // If we were looking at a lobby, say so: the server closes a lobby nobody joins in time.
          const wasWaiting = gameRef.current?.status === "waiting";
          setState({ phase: wasWaiting ? "lobby-expired" : "not-found", game: null, error });
          return;
        }
        if (error.status === 401) {
          forgetToken(code);
          setState({ phase: "no-access", game: null, error });
          return;
        }
        failures += 1;
        setReconnecting(true);
      }
      schedule();
    }

    function schedule() {
      const base = mode === "race" ? (document.hidden ? POLL_HIDDEN_MS : POLL_MS) : HEARTBEAT_MS;
      // After failures wait longer each time (3 s, 6 s, 10 s...) instead of hammering a server that is down.
      const delay = failures ? Math.min(base * 2 ** failures, Math.max(base, POLL_MAX_BACKOFF_MS)) : base;
      timer = setTimeout(poll, delay);
    }

    function onVisibilityChange() {
      if (!document.hidden) {
        clearTimeout(timer);
        poll(); // coming back to the tab: catch up at once
      }
    }

    schedule();
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      cancelled = true;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [code, polling, mode]);

  // Send one guess. Resolves to { ok: true } or { ok: false, error }; it never throws.
  const submit = useCallback(
    async (word) => {
      const token = tokenRef.current;
      changes.current += 1;
      try {
        // `index` is how many guesses we believe we have made. If the server disagrees
        // (a double click, a retried request) it refuses instead of using up a guess.
        const game = await submitGuess(code, token, word, gameRef.current.me.guesses.length);
        changes.current += 1;
        setState({ phase: "ready", game, error: null });
        return { ok: true };
      } catch (error) {
        if (["STALE_INDEX", "GAME_OVER", "NO_GUESSES_LEFT"].includes(error.code)) {
          // Our picture of the game was wrong: load the real one.
          try {
            const game = await getGame(code, token);
            changes.current += 1;
            setState({ phase: "ready", game, error: null });
          } catch {
            /* keep what we have; the original error is reported below */
          }
        }
        return { ok: false, error };
      }
    },
    [code],
  );

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  return { ...state, reconnecting, submit, retry };
}
