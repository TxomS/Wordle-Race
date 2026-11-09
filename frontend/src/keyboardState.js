// The color of each key on the on-screen keyboard: the best thing we know about
// that letter from your own guesses. Green beats yellow beats grey.

const RANK = { grey: 1, yellow: 2, green: 3 };

export function keyboardState(guesses) {
  const state = {};
  for (const guess of guesses) {
    [...guess.word].forEach((letter, i) => {
      const color = guess.colors[i];
      if (!state[letter] || RANK[color] > RANK[state[letter]]) state[letter] = color;
    });
  }
  return state;
}
