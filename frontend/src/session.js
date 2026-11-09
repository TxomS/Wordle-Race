// The player's secret token for each game, kept in sessionStorage.
//
// sessionStorage belongs to one browser tab: it survives a refresh, but a second
// tab (or window) starts empty. That is what lets two tabs of the same browser be
// two different players. Closing the tab forgets the token (a known limitation).
//
// Every access is wrapped in try/catch because browsers can refuse storage
// (private mode, blocked site data). The game then simply cannot be resumed.

const key = (code) => `wordle-race:token:${code}`;

export function saveToken(code, token) {
  try {
    sessionStorage.setItem(key(code), token);
  } catch {
    /* storage unavailable */
  }
}

export function loadToken(code) {
  try {
    return sessionStorage.getItem(key(code));
  } catch {
    return null;
  }
}

export function forgetToken(code) {
  try {
    sessionStorage.removeItem(key(code));
  } catch {
    /* storage unavailable */
  }
}
