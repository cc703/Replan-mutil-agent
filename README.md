# Replan Multi-Agent (minimal demo)

A small, deterministic Python CLI that demonstrates a coordinator assigning work to specialist agents, reacting to a blocked review, inserting a fallback task, and completing the plan.

## Requirements

- Python 3.8 or later
- No third-party packages, API keys, or network access

## Run

```bash
python main.py
```

The demo intentionally blocks the first review attempt so you can see the coordinator replan and retry. It is a local workflow example, not an LLM-powered agent or a web service.

## Environment setup

The dependency list is empty because the demo uses only Python's standard library. A cloud environment can use this install command:

```bash
python -m pip install -r requirements.txt
```

No start service is needed. To run the example, use `python main.py`.

## Configuration

No environment variables, credentials, or additional network domains are required. `.env.example` is intentionally empty apart from this note.
