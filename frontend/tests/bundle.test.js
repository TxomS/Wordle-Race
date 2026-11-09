// The brief says reviewers will "inspect the frontend bundle in devtools". This test does
// the same thing the cheap way: it reads the files the browser downloads and checks that
// the word lists are not inside them. The server alone decides what a valid word is, and
// shipping the lists would hand out every possible answer.
//
// Some ordinary English words (error, green, space...) appear in any program, so the test
// does not expect zero matches. It expects far fewer than a shipped list would produce:
// a bundled list would match every one of its words.
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const assets = path.join(import.meta.dirname, "..", "dist", "assets");
const wordsDir = process.env.WORDS_DIR ?? "/words";

const files = readdirSync(assets);
const shipped = files.filter((name) => name.endsWith(".js") || name.endsWith(".css") || name.endsWith(".html"));
const bundle = shipped.map((name) => readFileSync(path.join(assets, name), "utf8")).join("\n");
const tokens = new Set((bundle.match(/[A-Za-z]+/g) ?? []).map((token) => token.toLowerCase()));

const readWords = (file) => readFileSync(path.join(wordsDir, file), "utf8").split(/\s+/).filter(Boolean);
const matches = (words) => words.filter((word) => tokens.has(word)).length;

test("the check itself works: it can see words that really are in the bundle", () => {
  assert.ok(shipped.some((name) => name.endsWith(".js")), "the build produced no JavaScript");
  assert.ok(tokens.has("fetch"), "expected the word 'fetch' (used by api.js) to be found");
});

test("the possible answers are not in the shipped JavaScript", () => {
  assert.ok(existsSync(path.join(wordsDir, "answers.txt")), `no answers.txt in ${wordsDir}`);
  const answers = readWords("answers.txt");
  const found = matches(answers);
  assert.ok(found < answers.length * 0.25, `${found} of ${answers.length} answers appear in the bundle`);
});

test("the accepted-guess list is not in the shipped JavaScript", () => {
  const allowed = readWords("allowed.txt");
  const found = matches(allowed);
  assert.ok(found < allowed.length * 0.25, `${found} of ${allowed.length} allowed words appear in the bundle`);
});

test("no source maps or word files are served", () => {
  assert.deepEqual(
    files.filter((name) => name.endsWith(".map") || name.endsWith(".txt")),
    [],
  );
});
