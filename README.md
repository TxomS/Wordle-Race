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

Find the hidden 5-letter word in 6 guesses or less!<br>
Type on your keyboard or tap the on-screen keys to guess.<br>

🟩 Right letter, right place<br>
🟨 In the word, but somewhere else<br>
⬜ Not in the word<br>

**Play Solo:** Guess alone and see how fast you can get the word!
**Play Co-op:** Race your friend to see who can guess the word quicker!<br>
**Lost your tab?** No problem! Just give your friend the lobby code again to enter.

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
