"""Source hash v1 contract, mirrored from the add-on's build_identity.py.

Source hash v1 excludes generated packaging/dependency files and normalizes the
legacy-only bl_info assignment and text line endings. Git is only read at build
time by tools/build_identity.py; Blender never needs a checkout or network.
"""
import ast
import hashlib
import json
from pathlib import Path

EXPORT_API_VERSION = 1
EXCLUDED = {'build-info.json', 'dependency-lock.json', '_legacy_dependencies.json',
            'blender_manifest.toml', 'LICENSE', 'install_dependencies.py',
            'git_source_manager.py', 'legacy_dependencies.py'}


def source_hash(root):
    root = Path(root)
    if not (root / '__init__.py').is_file():
        raise ValueError('Add-on source directory is incomplete: ' + str(root))
    digest = hashlib.sha256()
    for path in sorted(Path(root).rglob('*')):
        relative = path.relative_to(root)
        if (not path.is_file() or any(p.startswith('.') or p in
                ('__pycache__', '_dependencies', 'wheels', '_host_tools') for p in relative.parts)
                or path.name in EXCLUDED or path.suffix in ('.pyc', '.blend1')):
            continue
        data = path.read_bytes()
        if path.suffix in ('.py', '.json', '.yaml', '.yml', '.toml', '.md', '.txt'):
            data = data.replace(b'\r\n', b'\n')
        if relative.as_posix() == '__init__.py':
            lines = data.decode('utf-8').splitlines(keepends=True)
            for node in reversed(ast.parse(data).body):
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'bl_info' for t in node.targets):
                    del lines[node.lineno - 1:node.end_lineno]
            data = ''.join(lines).encode('utf-8')
        digest.update(relative.as_posix().encode('utf-8') + b'\0')
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def read_identity(root):
    root = Path(root)
    identity = json.loads((root / 'build-info.json').read_text(encoding='utf-8'))
    if identity.get('schema_version') != 1 or identity.get('source_hash_version') != 1:
        raise ValueError('Unsupported add-on build identity schema')
    if identity.get('source_sha256') != source_hash(root):
        raise ValueError('Installed add-on files differ from their build identity; rebuild/reinstall the package')
    lock = (root / 'dependency-lock.json').read_bytes()
    if hashlib.sha256(lock).hexdigest() != identity.get('dependency_lock_sha256'):
        raise ValueError('Installed dependency lock differs from its build identity')
    return identity
