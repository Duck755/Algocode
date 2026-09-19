"""Small interactive select prompt with a green checkmark after selection."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style
from questionary.prompts.common import Choice, InquirerControl, Separator, create_inquirer_layout
from questionary.question import Question
from questionary.styles import merge_styles_default

_GREEN_CHECK_STYLE = Style.from_dict(
    {
        "qmark": "#5f819d",
        "question": "bold",
        "answer": "#FF9D00 bold",
        "success": "#00FF00 bold",
        "instruction": "",
        "pointer": "",
        "selected": "",
        "text": "",
    }
)


def select(
    message: str,
    choices: Sequence[str | Choice | Separator],
    default: Any = None,
) -> Question:
    """Create an arrow-key select question with a `?` -> green `✔` transition."""
    inquirer = InquirerControl(
        choices,
        default,
        pointer="»",
        use_indicator=True,
        use_shortcuts=False,
        show_selected=False,
        show_description=True,
        use_arrow_keys=True,
        initial_choice=default,
    )

    def get_prompt_tokens():
        qmark = ("class:success", "✔") if inquirer.is_answered else ("class:qmark", "?")
        tokens = [qmark, ("class:question", f" {message} ")]
        if inquirer.is_answered:
            pointed = inquirer.get_pointed_at()
            if isinstance(pointed.title, list):
                answer = "".join(token[1] for token in pointed.title)
            else:
                answer = str(pointed.title)
            tokens.append(("class:answer", answer))
        else:
            tokens.append(("class:instruction", " (Use arrow keys)"))
        return tokens

    layout = create_inquirer_layout(inquirer, get_prompt_tokens)

    bindings = KeyBindings()

    @bindings.add(Keys.ControlQ, eager=True)
    @bindings.add(Keys.ControlC, eager=True)
    def abort(event):
        event.app.exit(exception=KeyboardInterrupt, style="class:aborting")

    def move_cursor_down(event):
        inquirer.select_next()
        while not inquirer.is_selection_valid():
            inquirer.select_next()

    def move_cursor_up(event):
        inquirer.select_previous()
        while not inquirer.is_selection_valid():
            inquirer.select_previous()

    bindings.add(Keys.Down, eager=True)(move_cursor_down)
    bindings.add(Keys.Up, eager=True)(move_cursor_up)

    @bindings.add(Keys.ControlM, eager=True)
    def set_answer(event):
        inquirer.is_answered = True
        event.app.exit(result=inquirer.get_pointed_at().value)

    @bindings.add(Keys.Any)
    def other(event):
        """Ignore other keys instead of inserting text."""

    return Question(
        Application(
            layout=layout,
            key_bindings=bindings,
            style=merge_styles_default([_GREEN_CHECK_STYLE]),
        )
    )
