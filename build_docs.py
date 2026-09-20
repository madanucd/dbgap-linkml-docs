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


def _md_escape_cell(text) -> str:
    """Keep a value safe inside a markdown table cell (single line, no pipes)."""
    if text is None:
        return ''
    text = str(text).replace('|', '\\|').replace('\n', ' ').strip()
    return text


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
        lines.append(schema_desc)
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
            lines.append(class_desc)
            lines.append('')
        lines.append(f'{len(class_slots)} variable(s):')
        lines.append('')
        lines.append('| Variable | Type | Range | Total N | Description |')
        lines.append('|---|---|---|---|---|')
        for slot_key in class_slots:
            slot_def = slots.get(slot_key) or {}
            ann = slot_def.get('annotations') or {}
            range_val = slot_def.get('range', '')
            range_cell = range_val
            if range_val in enums:
                range_cell = f'[`{range_val}`](#{_slugify(range_val)}-enum)'
            else:
                range_cell = f'`{range_val}`'
            row = [
                f'`{slot_key}`',
                _md_escape_cell(ann.get('dbgap_type', '')),
                range_cell,
                _md_escape_cell(ann.get('count', '')),
                _md_escape_cell(slot_def.get('description', '')),
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
            'identical allowed values. Each variable\'s own observed '
            '`value_counts` are shown in its dataset table above via its '
            'annotations — enums here list only the allowed labels.'
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
