"""Reproducible OneNote (.onex) -> clean text extractor (BEST-EFFORT, ~66% fidelity).

A .onex single-file package is an OLE2 compound file. The prose lives inside the
`UnencryptedPackage` stream, but only ~66% of it is recoverable as UTF-8 readable
runs -- OneNote stores the rest in a compressed/structured OneStore form that
plain text extraction cannot reach. For full-fidelity notes, supply the clean
text file directly (however you exported it originally). This helper is a
convenience for .onex-only updates; expect to lose some content.

Usage:  python3.12 extract_onex.py [<input.onex>] [<output.txt>]
Defaults to the project .onex and the canonical clean-text path.
"""
import olefile, re, sys, pathlib, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from cogmap_paths import SOURCES

# ---- same cleaning rules prep uses, so downstream chunk texts stay stable ----
def clean_text(s):
    s = re.sub(r'HYPERLINK\s+"([^"]+)"', ' ', s)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = s.replace('\u2011', '-')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def is_readable(s):
    if len(s) < 30: return False
    printable = sum(1 for c in s if c.isprintable()) / max(1, len(s))
    letters = sum(1 for c in s if c.isalpha()) / max(1, len(s))
    weird = sum(1 for c in s if ord(c) > 127 and c not in '\u201c\u201d\u2018\u2019\u2014\u2013\u2026\u00e9\u00c9\u00e8\u00c8\u00e1\u00c1\u00ed\u00cd\u00f3\u00d3\u00fa\u00da\u00fc\u00dc\u00f1\u00d1') / max(1, len(s))
    return printable > 0.92 and letters > 0.35 and weird < 0.08

# readable-run pattern: printable ASCII + common latin/punct/quotes (>=20 chars
# gives best recoverable coverage of the OneStore prose)
RUN = re.compile(r'[\x20-\x7e\u00a0-\u024f\u2010-\u2060]{20,}')

def _entropy(b):
    if not b:
        return 0.0
    import math, collections
    cnt = collections.Counter(b)
    n = len(b)
    return -sum((c / n) * math.log2(c / n) for c in cnt.values())

def diagnose(path):
    """Return (package_bytes, entropy, looks_encrypted) for a best-effort reason
    when no prose is recoverable. High entropy (~8 bits/byte) means the package is
    encrypted / rights-managed; low entropy means it's near-empty or the prose is
    locked in an unrecoverable binary OneStore form."""
    pkg = b''
    encrypted_transform = False
    try:
        ole = olefile.OleFileIO(str(path))
        for s in ole.listdir():
            name = s[-1] if s else ''
            if name == 'UnencryptedPackage' or name == 'EncryptedPackage':
                try:
                    pkg = ole.openstream(s).read()
                except Exception:
                    pass
                if name == 'EncryptedPackage':
                    encrypted_transform = True
            # IRM / DataSpaces transform metadata signals rights management
            if name in ('TransformInfo',) or 'DRMTransform' in name or 'IRMDSTransform' in name:
                encrypted_transform = True
        ole.close()
    except Exception:
        pass
    ent = _entropy(pkg)
    looks_encrypted = encrypted_transform or ent > 7.0
    return pkg, ent, looks_encrypted

def extract(path):
    ole = olefile.OleFileIO(str(path))
    blob = bytearray()
    for s in ole.listdir():
        try:
            blob += ole.openstream(s).read()
        except Exception:
            pass
    ole.close()
    text = blob.decode('utf-8', 'ignore')
    runs = RUN.findall(text)
    out = []
    seen = set()
    for r in runs:
        r = clean_text(r)
        if not is_readable(r):
            continue
        key = re.sub(r'[^a-z0-9 ]', '', r.lower())
        key = re.sub(r'\s+', ' ', key).strip()[:200]
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out

def _fail(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        src = pathlib.Path(sys.argv[1])
    else:
        found = sorted(SOURCES.glob('*.onex'))
        if not found:
            print('No .onex file found in sources/. Pass one explicitly: '
                  'python extract_onex.py <input.onex> [output.txt]')
            sys.exit(1)
        src = found[0]
    dst = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else SOURCES / (src.stem + '.txt')

    if not src.exists():
        _fail(f'.onex not found: {src}')
    if not olefile.isOleFile(str(src)):
        _fail(f'{src.name} is not a valid OneNote .onex (OLE2) package; cannot convert. '
              f'Export a clean .md/.txt instead.')

    lines = extract(src)

    if not lines:
        # Nothing recoverable. Diagnose why and refuse to write an empty source that
        # would silently get ingested as a phantom note. Never clobber an existing
        # good .txt with an empty result.
        _pkg, ent, looks_encrypted = diagnose(src)
        if looks_encrypted:
            reason = ('the package appears encrypted / rights-managed (sensitivity label '
                      'or IRM protection), so its text cannot be read without opening it '
                      'in OneNote')
        else:
            reason = ('no readable prose is present -- the note is near-empty, image/ink-only, '
                      'or its text is stored in an unrecoverable binary OneStore form '
                      f'(package entropy {ent:.2f} bits/byte)')
        if dst.exists() and dst.stat().st_size > 0:
            _fail(f'{src.name}: recovered 0 notes ({reason}). '
                  f'Keeping the existing non-empty {dst.name} untouched. '
                  f'For reliable results, export a clean .md/.txt from OneNote and drop it in sources/.')
        # remove any stale empty file we or a prior run may have left behind
        if dst.exists() and dst.stat().st_size == 0:
            try: dst.unlink()
            except Exception: pass
        _fail(f'{src.name}: recovered 0 notes ({reason}). '
              f'No source file was written. '
              f'For reliable results, export a clean .md/.txt from OneNote (File > Export, '
              f'or copy the page text) and drop it in sources/.')

    # blank-line separated so the generic text chunker treats each note as its own chunk
    dst.write_text('\n\n'.join(lines), encoding='utf-8')
    print('extracted', len(lines), 'notes ->', dst)
