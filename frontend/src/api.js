// The only file that talks to the server. Everything else calls these functions.

// Give up on a request after this long, so the screen can say "cannot reach the server"
// instead of waiting forever on a connection that will never answer.
const REQUEST_TIMEOUT_MS = 10000;

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status; // HTTP status, or 0 when the server could not be reached
    this.code = code; // the server's stable error code, e.g. "NOT_A_WORD"
  }
}

async function request(method, path, { token, body } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["X-Player-Token"] = token;

  let response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch {
    throw new ApiError(0, "NETWORK", "Cannot reach the server.");
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    // The reply was not JSON (for example nginx's page when the backend is down).
  }

  if (!response.ok) {
    const error = data && data.error;
    throw new ApiError(
      response.status,
      error?.code ?? "SERVER_ERROR",
      error?.message ?? "The server had a problem.",
    );
  }
  return data;
}

export const createGame = (mode) => request("POST", "/games", { body: { mode } });

export const joinGame = (code) => request("POST", `/games/${code}/join`);

export const getGame = (code, token) => request("GET", `/games/${code}`, { token });

export const submitGuess = (code, token, guess, index) =>
  request("POST", `/games/${code}/guesses`, { token, body: { guess, index } });
