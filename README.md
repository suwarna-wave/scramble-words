# Scrambled Words

A polished offline word scramble game built with Python and `pygame`.

## Features

- Clean desktop GUI with a single stable game window
- Standard levels: 60 seconds, 45 seconds, and 25 seconds
- Custom timer section for practice runs
- Instant scoring for correct answers
- Full reset on wrong answer or when time runs out
- Built-in sound effects with no external sound files required
- Persistent high score saved in `scores.json`
- Bundled offline word bank with more than 2,000 words

## Run

Install the dependency:

```bash
pip install -r requirements.txt
```

Start the game:

```bash
python3 game.py
```

## Rules

1. Pick a standard level or set your own time.
2. A scrambled word appears on screen.
3. Type the correct word and press `Enter`.
4. A correct answer increases your score and loads the next word.
5. A wrong answer or expired timer ends the run and resets the game.
