## Race fairness

The first to solve ends the game, and the next guess gets `409 GAME_OVER`. Two winning guesses at the same moment therefore always produce exactly one winner. The server's order is the only one that counts; in a photo finish, network speed can still decide who arrives first.

**Considered.** Client timestamps and "fewest guesses wins".

## When a player disappears

A player is "Disconnected" when the server has not heard from them for 15 seconds (any request counts, including polling). There is **no forfeit**: the other player carries on and can still win. A newcomer who uses the game's code can **take over a disconnected seat**: they get the same board and a new token, and the old token stops working. I created the rules like this in case the player loses the tab or loses the token by closing the tab and/or chrome.

Abandoned games are removed by a background sweep that runs every minute:

| Game                         | Removed when                                                                                          |
| ---------------------------- | ----------------------------------------------------------------------------------------------------- |
| Being played                 | no guess for 15 min **and** no page has asked about it for 15 min                                     |
| Finished                     | the same as above, but 2 min                                                                          |
| Lobby (waiting for a friend) | waited 15 min even if the creator is still there, **or** the creator's page has been silent for 2 min |

**Considered.** A forfeit timer and ending the game when someone leaves.

## How a player learns about the opponent's progress

Polling: the page calls `GET /api/games/{code}` every 1.5 s (5 s in a hidden tab). The same call is the reconnect path: if the server cannot be reached the page shows "Reconnecting…", waits longer between tries, and carries on by itself.

**Considered.** Server-Sent Events and WebSockets but decided on this instead.

## What is in memory, what is saved, and what a restart does

On a restart no game is lost (checked with `docker compose restart` and with a hard kill mid-game). Open pages show "Reconnecting…" and resume on their own. The server forgets who was around, so a player not yet heard from gets a short benefit of the doubt: 15 s for the "Connected" label and 2 min before the clean-up may remove their game.

## Other choices

- **Scoring** is two passes: greens first, then yellows from the letters left over. It is tested with ABBEY and BABES example.
- **Solo is a race with one player** so there is one code path.
- **Room codes** are 5 characters from 31 symbols with no look-alikes (about 28 million codes).
- **Word lists** 100 answers, 3,285 allowed words. They are mounted from `backend/data`, so they can be swapped and restart the backend.

## Known limitations

- **One backend process.** Presence is in memory.
- **No rate limiting.** A random user could try codes and take a free or disconnected seat.
- **Taking over a seat is deliberately open.** Anyone who knows the code can take a disconnected seat and then sees that seat's own guessed words.
- **A creator who returns within 2 minutes of closing a lobby** gets the free seat, not the original one, so the race starts at once and the old creator seat stays a "ghost" until a friend takes it over.
- **Finished games vanish after about 2 to 3 minutes** so a reload after that shows "Game not found".
- **Colors are the only visual signal** for the result of a letter. Screen readers get text labels.
- **Plain HTTP, no accounts, no rematch, no spectators.**

## With more time

- Rate limits on joining and guessing.
- A rematch button and an explicit "resume" step for a lost tab.
- Resume or pause button to stop both players from progressing if needed.
- An optional hard mode, and optional letter patterns for color-blind players.
- A forfeit button between the races.
- A timer for both the single player and race modes, there for it would show which player won first and how long it took. While the single player would know how long it took them.
- With the timer feature added, a leaderboard to keep track of top 10 best times of completion.

## How I used AI tools

I built this with Claude Code. I first created an overview plan and then built it in small steps that I committed one at a time.

- **Planning and design:** I talked through each open decision with the assistant (storage, fairness, how to find out about the opponent, reconnecting, what happens when someone leaves, how long games live, the rules and choices a user can make).
- **Code and tests:** I had Claude create the skeleton and each feature and/or functionality and I tweaked it in my vision to help me get to the solution.
- **Checking its work:** nothing was accepted just because it was written. Every step was run: `make test`, and live checks in the browser with two tabs at each step.
- **My decisions:** I chose the polling approach, the game lifetimes, letting a newcomer take over a disconnected player's seat, the lobby rules, and the look of the buttons, and I tested the app by hand as I went. While Claude created most of the important pieces, I checked over its work and changed things to fit my end goal.
