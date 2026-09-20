#!/usr/bin/env python3
"""
build_docs.py

Turns a folder of LinkML *_schema.yaml files (one per dbGaP study, produced
by bdc2linkml.py) into a browsable static docs site — a study index page
plus one page per study showing its classes (datasets), slots (variables),
and enums (permissible values) — all navigable from a single sidebar via
mkdocs.

Usage:
    python build_docs.py                         # schemas/ -> docs/, refresh mkdocs.yml
    python build_docs.py --schemas-folder path    # custom schema source folder
    python build_docs.py --docs-folder path       # custom docs output folder

Then, from this project's root (where mkdocs.yml lives):
    mkdocs serve      # live-reload dev server at http://127.0.0.1:8000
    mkdocs build      # writes the static site to site/

Re-run this script any time you add/remove a *_schema.yaml file in
schemas/ — it regenerates every page AND mkdocs.yml's nav, so newly added
studies show up in the sidebar automatically.
"""

import argparse
import os
import re
import yaml


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _slugify(text: str) -> str:
    text = re.sub(r'[^a-zA-Z0-9]+', '-', str(text)).strip('-').lower()
    return text or 'schema'


def _study_id_from_schema(schema: dict, filename: str) -> str:
    ann = schema.get('annotations') or {}
    sid = ann.get('study_id')
    if sid:
        return str(sid)
    # Fallback: pull a phsNNNNNN-looking token out of the filename
    m = re.search(r'phs\d+', filename, re.IGNORECASE)
    return m.group(0) if m else os.path.splitext(filename)[0]


def _fmt_enum_pvs(enum_def: dict, max_shown: int = 25) -> str:
    pvs = list(((enum_def or {}).get('permissible_values') or {}).keys())
    if not pvs:
        return '_(no permissible values listed)_'
    shown = pvs[:max_shown]
    line = ', '.join(f'`{v}`' for v in shown)
    if len(pvs) > max_shown:
        line += f', _…and {len(pvs) - max_shown} more_'
    return line


def _md_escape_prose(text) -> str:
    """Escape square brackets in ordinary (non-table-cell) markdown prose,
    e.g. a schema or class description paragraph, for the same reason as
    _md_escape_cell — raw dbGaP text can contain '[...]' that would
    otherwise risk being parsed as link syntax."""
    if text is None:
        return ''
    return str(text).replace('[', '\\[').replace(']', '\\]').strip()


def _md_escape_cell(text) -> str:
    """
    Keep a value safe inside a markdown table cell: single line, no pipes
    (which would be parsed as extra column separators), and square brackets
    escaped (raw dbGaP text containing '[...]' can otherwise be misread as
    markdown link syntax, especially if a '(...)' follows it elsewhere on
    the same line).
    """
    if text is None:
        return ''
    text = str(text).replace('|', '\\|').replace('\n', ' ').strip()
    text = text.replace('[', '\\[').replace(']', '\\]')
    return text


def _html_escape(text) -> str:
    """Escape text for safe embedding inside raw HTML we construct (e.g.
    inside a <details> block within a markdown table cell). Also entity-
    encodes '|' and brackets so the table-row splitter and any accidental
    markdown link parsing can't misinterpret it either, since this text
    still lives on a single markdown-table source line."""
    if text is None:
        return ''
    text = str(text)
    text = (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('|', '&#124;')
                .replace('[', '&#91;')
                .replace(']', '&#93;')
                .replace('\n', ' '))
    return text.strip()


def _fmt_values_cell(value_counts_raw: str, comments: list, max_shown: int = 40) -> str:
    """
    Build a collapsible <details> cell showing this SLOT's own observed
    value=count breakdown (from its 'value_counts' annotation) plus any
    comments — the direct dataset-to-values connection, distinct from the
    enum's bare label list (which is shared across slots and carries no
    per-slot counts). Returns '—' if there's nothing to show.
    """
    pairs = []
    if value_counts_raw:
        pairs = [p.strip() for p in str(value_counts_raw).split(';') if p.strip()]

    if not pairs and not comments:
        return '—'

    body_parts = []
    if pairs:
        shown = pairs[:max_shown]
        body_parts.append('<br>'.join(_html_escape(p) for p in shown))
        if len(pairs) > max_shown:
            body_parts.append(f'&hellip; and {len(pairs) - max_shown} more')
    if comments:
        comment_text = '; '.join(_html_escape(c) for c in comments)
        body_parts.append(f'<em>Comment: {comment_text}</em>')

    summary = f'{len(pairs)} value(s)' if pairs else 'comment'
    body = '<br>'.join(body_parts)
    return f'<details><summary>{summary}</summary>{body}</details>'


# --------------------------------------------------------------------------- #
# Per-study page
# --------------------------------------------------------------------------- #

def _render_study_page(schema: dict, filename: str) -> str:
    study_id = _study_id_from_schema(schema, filename)
    schema_name = schema.get('name', filename)
    schema_desc = schema.get('description', '')
    schema_url = schema.get('id', '')

    classes = schema.get('classes') or {}
    slots = schema.get('slots') or {}
    enums = schema.get('enums') or {}

    lines = []
    lines.append(f'# {study_id}')
    lines.append('')
    if schema_desc:
        lines.append(_md_escape_prose(schema_desc))
        lines.append('')
    if schema_url:
        lines.append(f'**dbGaP study page:** [{schema_url}]({schema_url})')
        lines.append('')
    lines.append(f'**Source file:** `{filename}`')
    lines.append('')
    lines.append(
        f'This study has **{len(classes)}** dataset(s), **{len(slots)}** '
        f'unique variable(s), and **{len(enums)}** shared enum(s).'
    )
    lines.append('')
    lines.append('---')
    lines.append('')

    # ---- Datasets (classes) ----
    lines.append('## Datasets')
    lines.append('')
    for class_name in sorted(classes.keys()):
        class_def = classes[class_name] or {}
        class_slots = class_def.get('slots') or []
        class_anchor = _slugify(class_name)
        lines.append(f'### {class_name} {{#{class_anchor}}}')
        lines.append('')
        class_desc = class_def.get('description', '')
        if class_desc:
            lines.append(_md_escape_prose(class_desc))
            lines.append('')
        lines.append(f'{len(class_slots)} variable(s):')
        lines.append('')
        lines.append('| Variable | Variable ID(s) | Type | Range | Total N | Description | Values |')
        lines.append('|---|---|---|---|---|---|---|')
        for slot_key in class_slots:
            slot_def = slots.get(slot_key) or {}
            ann = slot_def.get('annotations') or {}
            range_val = slot_def.get('range', '')
            range_cell = range_val
            if range_val in enums:
                range_cell = f'[`{range_val}`](#{_slugify(range_val)}-enum)'
            else:
                range_cell = f'`{range_val}`'
            values_cell = _fmt_values_cell(
                ann.get('value_counts', ''),
                slot_def.get('comments') or [],
            )
            variable_ids_cell = _md_escape_cell(', '.join(ann.get('variable_ids') or []))
            row = [
                f'`{slot_key}`',
                variable_ids_cell,
                _md_escape_cell(ann.get('dbgap_type', '')),
                range_cell,
                _md_escape_cell(ann.get('count', '')),
                _md_escape_cell(slot_def.get('description', '')),
                values_cell,
            ]
            lines.append('| ' + ' | '.join(row) + ' |')
        lines.append('')

    # ---- Enums ----
    if enums:
        lines.append('---')
        lines.append('')
        lines.append('## Enums')
        lines.append('')
        lines.append(
            'Shared permissible-value sets, reused across variables with '
            'identical allowed values. Click **Values** in a dataset table '
            'above to see that specific variable\'s own observed counts — '
            'enums here list only the allowed labels, since the same enum '
            'can be shared by variables with different observed distributions.'
        )
        lines.append('')
        for enum_name in sorted(enums.keys()):
            enum_anchor = _slugify(enum_name) + '-enum'
            lines.append(f'### {enum_name} {{#{enum_anchor}}}')
            lines.append('')
            lines.append(_fmt_enum_pvs(enums[enum_name]))
            lines.append('')

    return '\n'.join(lines)


# --------------------------------------------------------------------------- #
# Index page
# --------------------------------------------------------------------------- #

def _render_index_page(study_rows: list) -> str:
    lines = []
    lines.append('# dbGaP → LinkML Schema Browser')
    lines.append('')
    lines.append(
        'LinkML schemas generated from dbGaP `var_report.xml` variable '
        'summaries, one per study. Pick a study from the sidebar, or the '
        'table below, to browse its datasets, variables, and enums.'
    )
    lines.append('')
    lines.append('| Study | Datasets | Variables | Enums | dbGaP link |')
    lines.append('|---|---|---|---|---|')
    for row in sorted(study_rows, key=lambda r: r['study_id']):
        page_link = f"[{row['study_id']}](studies/{row['slug']}.md)"
        dbgap_link = f"[link]({row['schema_url']})" if row['schema_url'] else ''
        lines.append(
            f"| {page_link} | {row['n_classes']} | {row['n_slots']} | "
            f"{row['n_enums']} | {dbgap_link} |"
        )
    lines.append('')
    return '\n'.join(lines)


# --------------------------------------------------------------------------- #
# mkdocs.yml
# --------------------------------------------------------------------------- #

def _write_mkdocs_yml(project_root: str, study_rows: list) -> None:
    nav_studies = [
        {row['study_id']: f"studies/{row['slug']}.md"}
        for row in sorted(study_rows, key=lambda r: r['study_id'])
    ]
    config = {
        'site_name': 'dbGaP LinkML Schema Browser',
        'theme': {
            'name': 'readthedocs',
        },
        'nav': [
            {'Home': 'index.md'},
            {'Studies': nav_studies},
        ],
        'markdown_extensions': [
            'tables',
            'attr_list',
        ],
    }
    path = os.path.join(project_root, 'mkdocs.yml')
    with open(path, 'w', encoding='utf-8') as fh:
        yaml.safe_dump(config, fh, sort_keys=False, default_flow_style=False)
    print(f'  \u2713 wrote {path}')


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def build(schemas_folder: str, docs_folder: str, project_root: str) -> None:
    if not os.path.isdir(schemas_folder):
        print(f'ERROR: schemas folder not found: {schemas_folder}')
        return

    schema_files = sorted(
        f for f in os.listdir(schemas_folder) if f.lower().endswith('.yaml')
    )
    if not schema_files:
        print(f'ERROR: no *.yaml schema files found in {schemas_folder}')
        return

    studies_dir = os.path.join(docs_folder, 'studies')
    os.makedirs(studies_dir, exist_ok=True)

    study_rows = []
    for filename in schema_files:
        filepath = os.path.join(schemas_folder, filename)
        with open(filepath, encoding='utf-8') as fh:
            schema = yaml.safe_load(fh) or {}

        study_id = _study_id_from_schema(schema, filename)
        slug = _slugify(study_id)

        page_md = _render_study_page(schema, filename)
        page_path = os.path.join(studies_dir, f'{slug}.md')
        with open(page_path, 'w', encoding='utf-8') as fh:
            fh.write(page_md)
        print(f'  \u2713 wrote {page_path}')

        study_rows.append({
            'study_id':   study_id,
            'slug':       slug,
            'n_classes':  len(schema.get('classes') or {}),
            'n_slots':    len(schema.get('slots') or {}),
            'n_enums':    len(schema.get('enums') or {}),
            'schema_url': schema.get('id', ''),
        })

    # Remove any stale per-study pages left over from a schema that's since
    # been removed/renamed in schemas_folder — otherwise they linger in
    # docs/studies/ forever, orphaned from mkdocs.yml's nav (mkdocs warns
    # about exactly this).
    current_slugs = {row['slug'] for row in study_rows}
    for existing in os.listdir(studies_dir):
        if not existing.lower().endswith('.md'):
            continue
        if os.path.splitext(existing)[0] not in current_slugs:
            stale_path = os.path.join(studies_dir, existing)
            os.remove(stale_path)
            print(f'  \u2717 removed stale {stale_path}')

    index_md = _render_index_page(study_rows)
    index_path = os.path.join(docs_folder, 'index.md')
    with open(index_path, 'w', encoding='utf-8') as fh:
        fh.write(index_md)
    print(f'  \u2713 wrote {index_path}')

    _write_mkdocs_yml(project_root, study_rows)

    print(f'\nDone. {len(study_rows)} study page(s) built.')
    print("Run 'mkdocs serve' from this project's root to preview, or 'mkdocs build' to output static HTML to site/.")


if __name__ == '__main__':
    ap = argparse.ArgumentParser(
        description='Build a static mkdocs site from LinkML *_schema.yaml files.'
    )
    ap.add_argument(
        '--schemas-folder', default='schemas',
        help='Folder containing *_schema.yaml files (default: schemas/)',
    )
    ap.add_argument(
        '--docs-folder', default='docs',
        help='Output folder for generated markdown pages (default: docs/)',
    )
    ap.add_argument(
        '--project-root', default='.',
        help="Where to write mkdocs.yml (default: current directory)",
    )
    args = ap.parse_args()
    build(args.schemas_folder, args.docs_folder, args.project_root)