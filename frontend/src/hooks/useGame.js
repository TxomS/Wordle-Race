import { useCallback, useEffect, useRef, useState } from "react";
import { getGame, submitGuess } from "../api.js";
import { forgetToken, loadToken } from "../session.js";

// Everything about one game that the screen needs: loading it, and sending guesses.
//
// phase:
//   "loading"    waiting for the server
//   "ready"      `game` holds the latest view from the server
//   "no-access"  this tab has no valid token for the game (it belongs to another tab)
//   "not-found"  no game with this code
//   "error"      the server could not be reached; `error` says why
//
// The server is the authority: the screen never changes the board by itself, it only
// shows the `game` the server last sent.
export function useGame(code) {
  const [state, setState] = useState({ phase: "loading", game: null, error: null });
  const [attempt, setAttempt] = useState(0); // bumped by retry() to load again
  const tokenRef = useRef(null);
  const gameRef = useRef(null);
  gameRef.current = state.game;

  useEffect(() => {
    let cancelled = false;
    const token = loadToken(code);
    tokenRef.current = token;

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

  // Send one guess. Resolves to { ok: true } or { ok: false, error }; it never throws.
  const submit = useCallback(
    async (word) => {
      const token = tokenRef.current;
      try {
        // `index` is how many guesses we believe we have made. If the server disagrees
        // (a double click, a retried request) it refuses instead of using up a guess.
        const game = await submitGuess(code, token, word, gameRef.current.me.guesses.length);
        setState({ phase: "ready", game, error: null });
        return { ok: true };
      } catch (error) {
        if (["STALE_INDEX", "GAME_OVER", "NO_GUESSES_LEFT"].includes(error.code)) {
          // Our picture of the game was wrong: load the real one.
          try {
            const game = await getGame(code, token);
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

  return { ...state, submit, retry };
}
