You are analysing `pallets/click` (tag {tag}, commit {sha}) to map its extension points for new CLI framework features.

Public names exported by `click/__init__.py`:
{public_names}

Below are excerpts of `click`'s core extension classes (`Command`, `Group`, `Parameter`, `Option`, `Context`, `ParameterSource`, `decorators`):
{excerpts}

Write a concise Markdown summary (under 400 words) of `click`'s extension points:
- `Option` and `Parameter` attributes and parsing (`handle_parse_result`, `consume_value`, `process_value`)
- `Context` and `ParameterSource` precedence
- `Command` / `Group` (including chained groups and `parse_args`)
- Interactive prompts and `CliRunner` testing hooks

Focus on where a new option/parameter/command-level feature can cleanly hook in without breaking existing behaviour.
