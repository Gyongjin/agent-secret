# agent-secret

Give secrets to one command, not to your coding agent.

When Claude Code, Codex or another agent runs `npm run dev` for you, it usually needs API keys. Putting them in `.env` or your shell means the agent can read them, print them into the chat log, or pick up a paid key for itself. `agent_secret.py` keeps the values in a file the agent never opens, and hands only the named ones to a single command.

```
python agent_secret.py run SUPABASE_URL,GROQ_API_KEY -- npm run dev
python agent_secret.py names
```

- Only the listed names go into that command's environment.
- Every value is replaced with `***` in the command's stdout and stderr.
- AI CLIs (`claude`, `codex`, `gemini`, also through `npx`/`bunx`/`pnpm dlx`/`yarn dlx`) are refused, so they can't bill an API key instead of your subscription.
- On Windows, `.cmd`/`.bat` targets with shell metacharacters (`& | < > ^ % !`) are refused, because `cmd.exe` would re-parse them.
- One file, standard library only, Python 3.8+, Windows/macOS/Linux.

## Setup

1. Put secrets in a JSON object or a `KEY=VALUE` file outside the repo, e.g. `~/.secrets/myapp.env`.
2. Point `AGENT_SECRET_FILE` at it (or pass `--file PATH` before `run`).
3. Tell your agent, in `CLAUDE.md` / `AGENTS.md`: "Never read the secret file. Run apps with `python agent_secret.py run NAME -- cmd`."
4. Deny reading the secret file in your agent's permission settings.

From Python: `from agent_secret import take; keys = take(["GROQ_API_KEY"])`.

## Limits

This reduces accidents; it is not a sandbox. A command you run can still print a value in a transformed form (base64, split across lines) or send it somewhere. Masking skips values shorter than 8 characters.

## Test

```
python -m unittest discover -s tests
```

## 한국어

AI 코딩 에이전트에게 API 키 값을 보여주지 않고, 이름을 적은 비밀값만 명령 하나에 넣어 실행하는 도구예요. 출력에 값이 찍히면 `***`로 가리고, claude·codex·gemini 같은 AI 도구에는 값을 넘기지 않아요.

## License

MIT
