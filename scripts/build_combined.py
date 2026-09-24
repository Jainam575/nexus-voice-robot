#!/usr/bin/env python3
"""
Build script: combines the Nexus robot package (nexus/*.py) into a single
standalone Python file (nexus_all_in_one.py) with no feature loss.

Transformations applied (each preserves exact runtime behaviour):
1. All relative imports (`from .x import ...`, at module or function level)
   are removed — every name lives in one namespace now.
   - main.py's `from .logging_config import logger` becomes
     `logger = logging.getLogger("Nexus")` (what setup_logging returned).
   - face_recognition.enroll_face's bare `from .camera import camera_manager`
     (the only statement in its `if` block) becomes `pass` — the global
     singleton is used, same as the original re-import.
2. Each module's `logger` variable is renamed to `logger_<module>` so every
   subsystem keeps its own log name (Nexus.Audio, Nexus.Motor, ...) instead
   of all silently sharing the last assignment.
3. config.py's `__file__`-based BASE_DIR/KNOWN_FACES_DIR (which pointed at
   nexus_package/ two levels up from nexus/config.py) now point at the
   directory containing this single script — known_faces/, vision_memory/
   and nexus_memory.json live next to it, exactly as before.
4. Module docstrings are kept verbatim as comment banners.
"""
import ast
import io
import os
import tokenize

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.environ.get("NEXUS_BUILD_SRC", _ROOT)
OUT = os.environ.get("NEXUS_BUILD_OUT", os.path.join(_ROOT, "nexus_all_in_one.py"))

# Dependency order: singletons defined before consumers run module-level code.
MODULES = [
    "config", "logging_config", "latency", "safety", "collision", "motor",
    "command_parser", "audio", "tts", "stt", "camera", "mood", "memory",
    "vision", "navigation", "face_display", "face_recognition", "games",
    "weather", "news", "shutdown", "safety_listener", "main",
]


def transform(module):
    path = os.path.join(SRC, "nexus", module + ".py")
    with open(path) as f:
        lines = f.readlines()

    tree = ast.parse("".join(lines))

    # ---- 1. remove relative imports ----
    replacements = {}  # lineno -> replacement code (or None to delete)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level > 0:
            lo, hi = node.lineno, node.end_lineno
            if module == "main" and node.module == "logging_config":
                indent = lines[lo - 1][:len(lines[lo - 1]) - len(lines[lo - 1].lstrip())]
                replacements[lo] = indent + 'logger = logging.getLogger("Nexus")\n'
            else:
                # Generic rule: if this import is the sole statement of a
                # block (the previous non-empty line ends with ':'),
                # deleting it would leave an empty if/try/for — use `pass`.
                prev = lines[lo - 2].rstrip() if lo >= 2 else ""
                if prev.endswith(":"):
                    indent = lines[lo - 1][:len(lines[lo - 1]) - len(lines[lo - 1].lstrip())]
                    replacements[lo] = indent + ("pass  # relative import removed "
                                                  "(global available)\n")
                else:
                    replacements[lo] = None
            for ln in range(lo + 1, hi + 1):  # multi-line import continuations
                replacements[ln] = None

    out = []
    for i, line in enumerate(lines, start=1):
        if i in replacements:
            rep = replacements[i]
            if rep is not None:
                out.append(rep)
            continue
        out.append(line)
    text = "".join(out)

    # ---- 2. rename `logger` -> `logger_<module>` (not in main) ----
    if module != "main":
        text_lines = text.splitlines(keepends=True)
        spans = []
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.NAME and tok.string == "logger":
                row, col = tok.start
                off = col + sum(len(l) for l in text_lines[:row - 1])
                spans.append((off, off + len("logger")))
        for start, end in reversed(spans):
            text = text[:start] + "logger_" + module + text[end:]

    # ---- 3. config.py __file__ path fixes ----
    if module == "config":
        old = "os.path.dirname(os.path.dirname(os.path.abspath(__file__)))"
        new = "os.path.dirname(os.path.abspath(__file__))"
        assert old in text, "config.py path pattern not found"
        text = text.replace(old, new)

    # ---- 4. docstring -> comment banner ----
    first = tree.body[0] if tree.body else None
    if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)):
        lo, hi = first.lineno, first.end_lineno
        doc_lines = text.splitlines()
        for ln in range(lo - 1, hi):
            stripped = doc_lines[ln].lstrip()
            indent = doc_lines[ln][:len(doc_lines[ln]) - len(doc_lines[ln].lstrip())]
            doc_lines[ln] = indent + "# " + stripped if stripped.strip() else indent + "#"
        text = "\n".join(doc_lines) + "\n"

    return text.strip("\n")


HEADER = '''#!/usr/bin/env python3
"""
Nexus Robot v3.0.0 — ALL-IN-ONE single-file build.

This file is the complete Nexus package (originally nexus/*.py, 23 modules
plus the run_nexus.py entry point) combined into ONE standalone Python
file with no features removed:

    config, logging_config, latency, safety, collision, motor,
    command_parser, audio, tts, stt, camera, mood, memory, vision,
    navigation, face_display, face_recognition, games, weather, news,
    shutdown, safety_listener, main

Behaviour notes (identical to the original package):
- Data folders live NEXT TO this script: known_faces/, vision_memory/ and
  nexus_memory.json are created/loaded from this file's own directory.
- The model files (ssd_mobilenet_v1_coco.tflite / detect.tflite,
  coco_labels.txt) and the wake-word file (hey-Nexus_...ppn) are looked up
  in the current working directory, exactly as before.
- Optional hardware/libraries (RPi.GPIO, cv2, numpy, pygame, tflite,
  pvporcupine, openai, webrtcvad, audioop) are all still optional and
  guarded — the file imports and runs on any machine, full features light
  up on the robot.
- Each subsystem keeps its original log name (Nexus.Audio, Nexus.Motor, ...).

Run it exactly like run_nexus.py:

    python3 nexus_all_in_one.py
"""

__version__ = "3.0.0"
'''


def main():
    sections = [HEADER]
    for m in MODULES:
        body = transform(m)
        banner = (
            "\n\n"
            + "# " + "=" * 74 + "\n"
            + f"# ======== MODULE: nexus/{m}.py " + "=" * max(1, 37 - len(m)) + "\n"
            + "# " + "=" * 74 + "\n"
        )
        sections.append(banner + body)
    combined = "\n".join(sections) + "\n"

    with open(OUT, "w") as f:
        f.write(combined)
    print(f"wrote {OUT}: {len(combined.splitlines())} lines")
    ast.parse(combined)  # syntax sanity check
    print("AST parse OK")


if __name__ == "__main__":
    main()
