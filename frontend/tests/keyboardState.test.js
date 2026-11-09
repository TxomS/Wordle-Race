// Tests use Node's built-in test runner, so they need no extra packages.
import assert from "node:assert/strict";
import test from "node:test";
import { keyboardState } from "../src/keyboardState.js";

const guess = (word, colors) => ({ word, colors });

test("each key shows the best color seen so far: green beats yellow beats grey", () => {
  const state = keyboardState([
    guess("after", ["grey", "grey", "yellow", "grey", "yellow"]),
    guess("storm", ["green", "green", "green", "green", "green"]),
  ]);
  assert.equal(state.a, "grey");
  assert.equal(state.t, "green"); // yellow first, then green
  assert.equal(state.r, "green");
  assert.equal(state.s, "green");
});

test("a key never falls back to a weaker color", () => {
  // E is green in the first guess and grey (a spare copy) in the second.
  const first = guess("crane", ["grey", "grey", "grey", "grey", "green"]);
  const second = guess("eerie", ["grey", "grey", "yellow", "grey", "grey"]);
  assert.equal(keyboardState([first, second]).e, "green");
  assert.equal(keyboardState([second, first]).e, "green");
});

test("letters that were never guessed have no color", () => {
  const state = keyboardState([guess("after", ["grey", "grey", "grey", "grey", "grey"])]);
  assert.equal(state.z, undefined);
  assert.deepEqual(keyboardState([]), {});
});
