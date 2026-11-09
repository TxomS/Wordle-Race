const ROWS = [
  ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
  ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
  ["Enter", "z", "x", "c", "v", "b", "n", "m", "Backspace"],
];

const LABELS = { Enter: "Enter", Backspace: "⌫" };

// `state` maps a letter to its best-known color. `onKey` receives a letter,
// "Enter" or "Backspace", the same values the physical keyboard produces.
export default function Keyboard({ state, onKey, disabled }) {
  return (
    <div className="keyboard" role="group" aria-label="On-screen keyboard">
      {ROWS.map((row, index) => (
        <div className={index === 1 ? "keyboard__row keyboard__row--inset" : "keyboard__row"} key={index}>
          {row.map((key) => {
            const wide = key.length > 1;
            const classes = ["key", wide ? "key--wide" : ""];
            if (state[key]) classes.push(`key--${state[key]}`);
            return (
              <button
                key={key}
                type="button"
                className={classes.filter(Boolean).join(" ")}
                disabled={disabled}
                aria-label={key === "Backspace" ? "Delete" : key}
                // Keep focus where it is, so pressing Enter on the real keyboard later
                // does not "click" the key that was last tapped.
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => onKey(key)}
              >
                {LABELS[key] ?? key}
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}
