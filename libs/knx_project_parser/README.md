# knx_project_parser

`knx_project_parser` is a small Python library inside the monorepo workspace for reading ETS `.knxproj`
archives and exporting a structured YAML view of the project.

## What It Parses

- project metadata from `project.xml`
- areas, lines, and device instances from `0.xml`
- group addresses with formatted KNX address notation
- product names and order numbers from manufacturer `Hardware.xml`
- communication object links to group addresses

## Usage

Run from the repository root:

```bash
uv sync
uv run --package knx-project-parser knx-project-parser /path/to/project.knxproj
```

Example:

```bash
uv run --package knx-project-parser knx-project-parser ./.local/Выстовка.knxproj > ./.local/Выстовка.knxproj.yaml
```

## Testing

```bash
uv run --package knx-project-parser pytest libs/knx_project_parser/tests
```
