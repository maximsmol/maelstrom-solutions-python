# Maelstrom Challenges in Python

## Challenges

See https://fly.io/dist-sys/ and https://github.com/jepsen-io/maelstrom

## Python Framework

[`/api`](./api/) provides a Python 3.11 framework for solving the challenges

1. Add the repository root to the PYTHONPATH (`sys.path`)
2. Inherit the `NodeBase` class and provide handler methods
3. Instantiate the handler class and call `.run` (in an async context)

See [`/echo/main.py`](./echo/main.py) for an example

## Optional Tooling

- [Conda (miniconda)](https://docs.conda.io/) for managing python installationsen/latest/miniconda.html
- [direnv](https://direnv.net/) for loading a Conda environment automatically
- [Just](https://github.com/casey/just/) for running commands
- [`dev-requirements.txt`](./dev-requirements.txt) lists formatters and linters recommended for development

## Copying/License

This software is quad-licensed and downstream users are free to use any of the provided licenses.

**Available licenses:**

| Name           | Requirements | [OSI][1] Approved      | Notes                                                                  |
| -------------- | ------------ | ---------------------- | ---------------------------------------------------------------------- |
| [MIT][2]       | Attribution  | :white_check_mark: Yes | Most commonly recognized and understood                                |
| [BSD0][3]      | None         | :white_check_mark: Yes | Unencumbered license allowed at Google                                 |
| [CC0][4]       | None         | :x: No                 | Preferred way of dedicating software to the public domain              |
| [Unlicense][5] | None         | :white_check_mark: Yes | OSI approved public domain dedication. **Questionable legal standing** |

[1]: https://opensource.org/
[2]: ./MIT-LICENSE
[3]: ./BSD0-LICENSE
[4]: ./COPYING
[5]: ./UNLICENSE
