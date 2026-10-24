# Contributing

This is a personal portfolio of seventy-seven prototypes, so it is small on purpose. The most useful thing you can send is a report that something does not run, or does not match what its README says.

## Reports I want

- **A number that does not match its script.** Every green-tagged number in a README is printed by a script in that project's `src/` folder. If you run the script and see a different number, open an issue with the project, the number the README gives, and the number you got.
- **A script that fails.** The step scripts use the standard library and run on Python 3.9 or newer. Include your Python version and the last lines of the error.
- **A broken link or a demo that does not load.**

## Check the repo before you send anything

From the repo root:

```bash
python3 tools/check_repo.py --exclude 02   # every project except 02, standard library only
python3 tools/check_repo.py 26             # one project
```

Project 02 also needs `numpy`, `pandas` and `scipy`. The check runs each project on a clean copy of its folder and covers the step scripts, the data generators, links, the demo scripts, the tests, and whether the green numbers in each README appear in what the scripts print. GitHub Actions runs it on Python 3.9 and 3.12 for every push.

## Pull requests

Fixes are welcome: a wrong number, a broken script, a typo, a clearer sentence. For anything larger, open an issue first so we agree on it before you spend time.

A change should keep to how the repo works:

- A number carries a tag: 🟢 measured (a script prints it), 🟡 modeled (the assumption is named beside it) or 🔴 hypothetical (designed, never tested).
- Data stays synthetic. The one exception is the public log that StepScout's real-data mode reads; it is fetched on demand and never committed.
- The data generators are seeded, and running one twice gives identical files. If you change a generator, regenerate the files it writes and commit them with the change.
- One project per commit, with a subject that names the project.

## Licence

The code is MIT licensed, and your contribution is under the same licence. The public log that StepScout's real-data mode reads is not part of this repo; it is under its own terms, summarized in `26-stepscout-task-mining-agent-candidates/data/real/README.md`.
