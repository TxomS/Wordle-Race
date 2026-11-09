import { useRef } from "react";
import Tile from "./Tile.jsx";

// A grid of maxGuesses rows. `guesses` are the rows the server has scored: each has
// `colors`, and `word` only on your own board. `typed` is the row you are typing now.
// size="small" is the compact version used for the opponent.
export default function Board({ guesses, typed = "", maxGuesses, wordLength, shake = false, size, label }) {
  // Only rows that arrive after the board first appeared get the flip animation, so a
  // refresh does not replay the whole game.
  const initialCount = useRef(guesses.length);

  const rows = [];
  for (let row = 0; row < maxGuesses; row += 1) {
    const guess = guesses[row];
    const isCurrent = row === guesses.length;
    const rowClass = isCurrent && shake ? "board__row board__row--shake" : "board__row";

    rows.push(
      <div className={rowClass} key={row} role="group" aria-label={`Guess ${row + 1}`}>
        {Array.from({ length: wordLength }, (_, col) =>
          guess ? (
            <Tile
              key={col}
              letter={guess.word?.[col]}
              color={guess.colors[col]}
              animate={row >= initialCount.current}
              delay={col * 250}
            />
          ) : (
            <Tile key={col} letter={isCurrent ? typed[col] : undefined} />
          ),
        )}
      </div>,
    );
  }

  return (
    <div className={size === "small" ? "board board--small" : "board"} role="group" aria-label={label}>
      {rows}
    </div>
  );
}
