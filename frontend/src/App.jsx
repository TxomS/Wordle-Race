import { useCallback, useEffect, useState } from "react";
import Game from "./screens/Game.jsx";
import Home from "./screens/Home.jsx";

// Two pages, so no router library: "/" is the home screen, "/g/ABCDE" is a game.
// nginx serves index.html for every path, which is why refreshing on a game URL works.
const GAME_PATH = /^\/g\/([A-Za-z0-9]{5})\/?$/;

function usePath() {
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const onBackOrForward = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onBackOrForward);
    return () => window.removeEventListener("popstate", onBackOrForward);
  }, []);

  const navigate = useCallback((to) => {
    window.history.pushState({}, "", to);
    setPath(to);
  }, []);

  return [path, navigate];
}

export default function App() {
  const [path, navigate] = usePath();
  const match = GAME_PATH.exec(path);
  const code = match ? match[1].toUpperCase() : null;

  useEffect(() => {
    document.title = code ? `Game ${code} - Wordle Race` : "Wordle Race";
  }, [code]);

  return (
    <>
      <header className="app-header">
        <button type="button" className="app-title" onClick={() => navigate("/")}>
          Wordle Race
        </button>
        {code && <span className="app-code">Game {code}</span>}
      </header>
      <main className="app-main">
        {code ? <Game key={code} code={code} navigate={navigate} /> : <Home navigate={navigate} />}
      </main>
    </>
  );
}
