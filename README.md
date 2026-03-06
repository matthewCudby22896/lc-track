# lc-track

A command-line tool for tracking LeetCode study progress. Allows the user to records _entries_ with a confidence (0-5) each time they study a problem. Problems are then re-scheduled for study using the  [SM2](https://en.wikipedia.org/wiki/SuperMemo) algorithm.

#### Built with:

- python3
- SQLite
- and the [typer](https://typer.tiangolo.com/) library.

#### Commands

<img width="940" height="567" alt="lc-track CLI help menu" src="https://github.com/user-attachments/assets/e6e6b955-2c7c-40be-9ee3-e74fc9ccad50" />

#### Confidence levels

| Level | Name | Description |
| :--- | :--- | :--- |
| **0** | **Complete Failure** | No recall; unable to formulate a solution. |
| **1** | **Recognised** | Failed the problem, but the solution was understood upon review. |
| **2** | **Near Miss** | Failed to pass, but was very close to a functional implementation. |
| **3** | **Strenuous** | Correct solution, but required significant mental effort or time. |
| **4** | **Proficient** | Correct solution; implemented with minor hesitation or thought. |
| **5** | **Perfect** | Instant, effortless recall and flawless implementation. |

#### Commands I keep forgetting

```shell
# Execute the CLI directly via Python
python3 -m src.lc.track

# Install the project in editable (development) mode
pip3 install -e .

# Run static type checking
mypy

# Run the linter
ruff check . --fix
