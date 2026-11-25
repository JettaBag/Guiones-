#!/usr/bin/env python3
"""Atajo: python editar.py crudos/video.mp4  (o crudos/video.json). Todo el proceso está en herramientas/editar.py."""
import runpy, sys
from pathlib import Path
sys.argv[0] = str(Path(__file__).parent / "herramientas" / "editar.py")
runpy.run_path(sys.argv[0], run_name="__main__")
