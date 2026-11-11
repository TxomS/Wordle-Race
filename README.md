## Wordle Race

Guess the hidden five-letter word in six tries or fewer.
Race your friends or test your skills alone.

## Quickstart

You only need `git`, `make` and Docker (with Compose v2). No local Python or Node.

```bash
git clone https://github.com/TxomS/Wordle-Race.git
cd Wordle-Race
make setup
```

Then open <http://localhost:8080>.
If you wish to use another one: `make setup WEB_PORT=9090`.

The first run builds the images and takes a few minutes. `make setup` returns when everything is healthy and prints the address.

## How to play

- **Goal:** Find the hidden 5-letter word in 6 guesses. Type on your keyboard or tap the on-screen keys; Enter submits.
- **Colors:** green means right letter, right place. Yellow means the letter is in the word, but somewhere else. Grey means it is not in the word, or all its copies are already accounted for. A letter is marked only as many times as it appears in the word, greens first (the word ABBEY and the guess BABES give yellow, yellow, green, green, grey).
- **Play Solo:** the server picks a word and you play alone.
- **Play Co-op:** you get a 5-character code and a link. Your friend opens the link and clicks "Join this game", or types the code into the Join box on the home page. The race starts the moment they join. You each see the other's progress as colored squares and whether they are connected. The first player to solve it wins; if both run out of guesses it is a draw.
- **Refresh:** reloading the page puts you back in your game.
- **Lost your tab?** If a player has been silent for 15 seconds their seat shows "Disconnected". Anyone who uses the game's code can take that seat and carries on from the same board, so closing the tab and using the code again gets you back in. A seat is only taken over when its player is disconnected, never in a solo game, and never after the game has ended.

## Make targets

| Command      | What it does                                                                                       |
| ------------ | -------------------------------------------------------------------------------------------------- |
| `make setup` | Builds the images, starts everything and waits until it is healthy                                 |
| `make test`  | Builds and runs all tests in containers (backend, then frontend). Exits non-zero if any test fails |
| `make down`  | Stops everything. The game database is kept                                                        |
| `make clean` | Stops everything and deletes all state: containers, network and the database volume                |

## Structure

```
.
├── Makefile                 setup | test | down | clean | logs
├── docker-compose.yml       backend + frontend (+ the test containers under a "test" profile)
├── DESIGN.md                decisions, trade-offs, limitations
├── backend/
│   ├── Dockerfile           multi-stage: runtime image and test image
│   ├── data/                answers.txt and allowed.txt (the word lists)
│   ├── app/
│   │   ├── rules.py         pure game rules: scoring, end conditions, winner (no HTTP, no storage)
│   │   ├── views.py         the only place that builds what the browser may see
│   │   ├── service.py       the use cases: create, join, guess, clean up
│   │   ├── store.py         SQLite persistence
│   │   ├── presence.py      who has been heard from recently (in memory)
│   │   ├── sweeper.py       background timer for the clean-up
│   │   ├── words.py         loads and checks the word lists
│   │   ├── api.py           HTTP routes and error mapping
│   │   ├── config.py        settings from environment variables
│   │   └── main.py          builds the app
│   └── tests/               pytest: rules, scoring, store, views, API, races, presence, sweep
└── frontend/
    ├── Dockerfile           builds the site with Node, serves it with nginx
    ├── nginx.conf           serves the app and proxies /api to the backend
    ├── src/                 React app (screens, components, the game hook, the API client)
    └── tests/               Node tests: keyboard colors and a check that no word list is shipped
```
