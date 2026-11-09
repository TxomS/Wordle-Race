// What the player reads for each error the server (or the network) can produce.

const MESSAGES = {
  BAD_FORMAT: "Not enough letters",
  NOT_A_WORD: "Not in word list",
  GAME_OVER: "The game is already over",
  NO_GUESSES_LEFT: "You have no guesses left",
  STALE_INDEX: "Your board was out of date. Try again",
  GAME_NOT_STARTED: "Waiting for your opponent to join",
  ROOM_FULL: "That game already has two players",
  NOT_FOUND: "No game with that code",
  NOT_IN_GAME: "You are not part of this game",
  NETWORK: "Cannot reach the server. Check your connection",
};

// True when the problem is the connection or the server, not something the player did.
export function isConnectionProblem(error) {
  return error?.code === "NETWORK" || error?.status >= 500;
}

export function messageFor(error) {
  if (isConnectionProblem(error)) return MESSAGES.NETWORK;
  return MESSAGES[error?.code] ?? "Something went wrong. Please try again";
}
