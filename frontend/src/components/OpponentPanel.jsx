import Board from "./Board.jsx";

// The opponent's side of a race. The server only ever sends their tile colors, so the
// board below has no letters to show, however it is drawn.
export default function OpponentPanel({ opponent, maxGuesses, wordLength }) {
  return (
    <section className="opponent" aria-label="Opponent">
      <div className="opponent__info">
        <h2 className="opponent__title">Opponent</h2>
        <p className={opponent.connected ? "presence presence--on" : "presence presence--off"} role="status">
          <span className="presence__dot" aria-hidden="true" />
          {opponent.connected ? "Connected" : "Disconnected"}
        </p>
        <p className="opponent__count">
          {opponent.guesses.length} of {maxGuesses} guesses
        </p>
      </div>
      <Board
        label="Opponent's board, colors only"
        guesses={opponent.guesses}
        maxGuesses={maxGuesses}
        wordLength={wordLength}
        size="small"
      />
    </section>
  );
}
