"""AASHA AIOS — Master Batch Compiler for 7 Gold-Standard STEM Bottleneck Chapters.

Runs compilation for all 7 chapters in deterministic sequence:
  1. class6_math_ch07_fractions
  2. class6_math_ch10_integers
  3. class8_math_ch02_linear_equations
  4. class8_math_ch09_algebraic_expressions
  5. class6_science_ch02_components_of_food
  6. class8_science_ch04_combustion_and_flame
  7. class10_science_ch09_heredity_evolution
"""

import sys
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent

CHAPTER_MODULES = [
    "build_fraction_chapter.py",
    "chapter_gen_integers.py",
    "chapter_gen_linear_eq.py",
    "chapter_gen_algebra.py",
    "chapter_gen_food.py",
    "chapter_gen_combustion.py",
    "chapter_gen_heredity.py",
]

def compile_all():
    print("=" * 60)
    print("AASHA AIOS — MASTER 7-CHAPTER GOLD BATCH COMPILATION")
    print("=" * 60)
    success = 0
    for mod in CHAPTER_MODULES:
        script_path = SCRIPTS_DIR / mod
        print(f"\n[Compiling] {mod}...")
        res = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True, cwd=str(SCRIPTS_DIR.parent))
        if res.returncode == 0:
            print(f"  ✓ SUCCESS: {mod}")
            success += 1
        else:
            print(f"  ✗ FAILED: {mod}")
            print(res.stderr)
            sys.exit(1)

    print("\n" + "=" * 60)
    print(f"BATCH COMPILATION COMPLETE: {success}/{len(CHAPTER_MODULES)} CHAPTERS COMPILED (100% GREEN)")
    print("=" * 60)

if __name__ == "__main__":
    compile_all()
