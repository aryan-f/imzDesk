# Documentation style

Follow the [Google developer documentation style guide](https://developers.google.com/style)
for all hand-written imzDesk documentation. The following rules summarize the
guidance that applies most often to this project.

## Voice and language

- Address the reader as "you."
- Use active voice and present tense.
- Use clear, direct language that works for a global audience.
- Prefer short sentences and paragraphs.
- Avoid slang, figurative language, and culture-specific references.
- Avoid words such as "easy," "just," "please," and "simply" in procedures.
- Define abbreviations on first use unless the abbreviation is more familiar
  than its expansion.

## Titles and headings

- Use sentence case.
- Give every page one unique level-one heading.
- Use a bare infinitive for a task title, such as "Register WSI and MSI data."
- Use a noun phrase for a conceptual title, such as "Registration transforms."
- Preserve the heading hierarchy without skipping levels.
- Do not use links, code formatting, or sequence numbers in headings.

## Procedures

- Explain the purpose or context before the steps when it is not already clear.
- State prerequisites before the procedure.
- Use numbered lists for sequences and bulleted lists for unordered choices.
- Start each step with an imperative verb.
- Put the goal before the action when a step needs both.
- Describe an action's result after the action.
- Mark nonrequired steps with "Optional:"
- State the expected result after the procedure when verification is useful.

## User interface text

- Match labels, capitalization, and punctuation in the application.
- Use bold text for visible interface labels.
- Use the interaction verb that matches the control, such as "select,"
  "enter," or "drag."
- Provide enough context to identify a control without relying on its location
  alone.

## Code and commands

- Use code formatting for filenames, paths, commands, parameters, class names,
  function names, and literal values.
- Introduce each code block with a complete sentence.
- Add a language identifier to fenced code blocks.
- Keep examples focused on the documented task.
- Use descriptive uppercase placeholders and explain each placeholder.
- Do not include a shell prompt in commands that readers can copy.

## Links and media

- Use link text that describes the destination.
- Do not use phrases such as "click here."
- Add useful alternative text to every informative image.
- Do not rely on color or position alone to communicate meaning.
- Introduce screenshots and explain what the reader should notice.

## API reference

- Write API prose in the source docstring, not in a generated Markdown page.
- Use NumPy-style docstrings consistently.
- Identify types with their fully qualified names when the type is not imported
  by the documented module.
- Document observable behavior, assumptions, errors, and return values.
- Avoid promising behavior that the implementation does not guarantee.

After changing a public docstring, regenerate the API reference:

```shell
uv run --group docs python tools/generate_api_docs.py
```

To verify that the committed reference is current, run the generator in check
mode:

```shell
uv run --group docs python tools/generate_api_docs.py --check
```
