// One square of the board. `letter` is missing on the opponent's board: it is only
// ever given colors, so it has no letters to show.

const MEANING = {
  green: "correct",
  yellow: "in the word, wrong place",
  grey: "not in the word",
};

export default function Tile({ letter, color, animate = false, delay = 0 }) {
  const classes = ["tile"];
  if (color) classes.push(`tile--${color}`);
  else if (letter) classes.push("tile--filled");
  if (animate) classes.push("tile--flip");

  const spoken = letter ? letter.toUpperCase() : "";
  const label = color ? [spoken, MEANING[color]].filter(Boolean).join(", ") : spoken || "empty";

  return (
    <div
      className={classes.join(" ")}
      style={animate ? { animationDelay: `${delay}ms` } : undefined}
      role="img"
      aria-label={label}
    >
      {spoken}
    </div>
  );
}
