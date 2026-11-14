"""AASHA AIOS — Phase 2 Batch Chapter Scaling Orchestrator.

Compiles full-depth, rich interactive offline learning modules for the 7 Middle School
STEM bottleneck chapters:
  1. Math Class 6 Ch 7: Fractions (F24 Fraction Slices, AVR-P302)
  2. Math Class 6 Ch 10: Integers (F25 Number-Line Hunter, AVR-P301)
  3. Math Class 8 Ch 2: Linear Equations in One Variable (F26 Dynamic Balance Scale, AVR-P316)
  4. Math Class 8 Ch 9: Algebraic Expressions and Identities (F20 Geometric Tile Area Model, AVR-P303)
  5. Science Class 6 Ch 2: Components of Food (F14 Chemical Reagent Spotter Lab, AVR-P401 / AVR-P306)
  6. Science Class 8 Ch 4: Combustion and Flame (F11 Fire Triangle & Flame Zones, AVR-P311)
  7. Science Class 10 Ch 9: Heredity and Evolution (F21 Mendelian Punnett Square Simulator, AVR-P321-bio)

Zero Token Bleed Invariant:
  100% compiled using Tier 0 Offline Synthesizer & Local URIRA Foundations.
  Cost: $0.0000 USD.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

# Setup paths to access aasha package in Aasha-AI/aasha-pipeline-with-master-json
REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = REPO_ROOT / "Aasha-AI" / "aasha-pipeline-with-master-json"
SRC_PATH = PIPELINE_DIR / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

# Ensure offline environment
os.environ["AASHA_OFFLINE"] = "1"
os.environ["ALLOW_PAID_GEMINI_FALLBACK"] = "false"

import fitz  # PyMuPDF
from aasha.config import Config
from aasha.pipeline.orchestrator import Orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("batch_compiler")


# Target chapter specifications with authentic pedagogical content
CHAPTERS_SPEC = [
    {
        "id": "class6_math_ch07_fractions",
        "title": "Fractions — Understanding Parts, Slices and Equivalency",
        "filename": "class6_fractions.pdf",
        "subject": "math",
        "grade": 6,
        "sim_id": "AVR-P302",
        "sim_name": "Fraction Strip & Slices Visualizer",
        "pages": [
            {
                "heading": "1. What is a Fraction? Fraction as Part of a Whole",
                "text": (
                    "A fraction represents part of a whole or a collection of objects. When an object is divided "
                    "into equal parts, each part is a fraction of the whole. In a fraction a/b, the top number 'a' is "
                    "called the Numerator (अंश), which tells how many equal parts are taken. The bottom number 'b' is "
                    "called the Denominator (हर), which tells the total number of equal parts into which the whole is divided. "
                    "For example, if a circular roti or pizza is divided into 4 equal slices and 3 are taken, the fraction is 3/4. "
                    "A proper fraction is always strictly less than 1, where the numerator is smaller than the denominator."
                ),
            },
            {
                "heading": "2. Equivalent Fractions, Simplest Form and Number Line Models",
                "text": (
                    "Equivalent fractions represent the same portion of the whole even though they have different numerators "
                    "and denominators. For instance, 1/2, 2/4, 3/6, and 4/8 all denote the exact same value. "
                    "To find equivalent fractions, multiply or divide both numerator and denominator by the same non-zero number. "
                    "To represent fractions on a number line, divide the unit interval between 0 and 1 into 'b' equal parts. "
                    "An improper fraction has a numerator greater than or equal to its denominator (e.g., 7/4 = 1 3/4). "
                    "Addition of fractions with like denominators adds numerators directly: a/c + b/c = (a+b)/c."
                ),
            },
        ],
    },
    {
        "id": "class6_math_ch10_integers",
        "title": "Integers — Positive and Negative Numbers on a Number Line",
        "filename": "class6_integers.pdf",
        "subject": "math",
        "grade": 6,
        "sim_id": "AVR-P301",
        "sim_name": "Number Line Marker & Hunter",
        "pages": [
            {
                "heading": "1. Introduction to Negative Numbers and the Set of Integers",
                "text": (
                    "In daily life we encounter opposite situations: profit and loss, above sea level and below sea level, "
                    "temperatures above zero and temperatures below zero. Positive numbers are written with a plus sign (+) or no sign. "
                    "Negative numbers are written with a minus sign (-). The collection of numbers comprising natural numbers, "
                    "zero, and negative natural numbers {... -3, -2, -1, 0, 1, 2, 3 ...} forms the set of Integers (पूर्णांक). "
                    "Zero is an integer which is neither positive nor negative. Every positive integer is greater than every negative integer."
                ),
            },
            {
                "heading": "2. Representation and Operations on the Number Line",
                "text": (
                    "On a horizontal number line, zero is marked in the center. Positive integers lie to the right of zero, "
                    "and negative integers lie to the left. Moving to the right increases value, while moving to the left decreases value. "
                    "Thus, -1 > -5 because -1 lies to the right of -5. "
                    "To add a positive integer, move to the right. To add a negative integer, move to the left. "
                    "Opposite integers like (+5) and (-5) add up to zero and are called additive inverses of each other."
                ),
            },
        ],
    },
    {
        "id": "class8_math_ch02_linear_equations",
        "title": "Linear Equations in One Variable — Balance Scale & Transposition",
        "filename": "class8_linear_equations.pdf",
        "subject": "math",
        "grade": 8,
        "sim_id": "AVR-P316",
        "sim_name": "Dynamic Balance Scale & Equilibrium System",
        "pages": [
            {
                "heading": "1. Algebraic Equations and the Principle of Equality",
                "text": (
                    "An algebraic equation is an equality involving variables. It has an equality sign (=) that separates "
                    "the expression on the left (Left Hand Side or LHS) from the expression on the right (Right Hand Side or RHS). "
                    "In a linear equation in one variable, the highest power of the variable appearing in the equation is strictly 1. "
                    "An equation is like a weighing balance in equilibrium: the value of LHS is exactly equal to the value of RHS. "
                    "If identical operations are performed on both sides, the balance remains undisturbed."
                ),
            },
            {
                "heading": "2. Solving Equations by Transposition and Applications",
                "text": (
                    "To solve an equation, we isolate the variable on one side. When a number moves from one side of the equation "
                    "to the other side, its sign changes. This operation is called Transposition (पक्षांतरण). "
                    "Addition changes to subtraction (+ becomes -), subtraction changes to addition (- becomes +), "
                    "multiplication changes to division (* becomes /), and division changes to multiplication. "
                    "When solving word problems, assign a variable x to the unknown quantity and translate statements into an equation."
                ),
            },
        ],
    },
    {
        "id": "class8_math_ch09_algebraic_expressions",
        "title": "Algebraic Expressions and Standard Identities",
        "filename": "class8_algebraic_expressions.pdf",
        "subject": "math",
        "grade": 8,
        "sim_id": "AVR-P303",
        "sim_name": "Shape Transformer & Geometric Tile Model",
        "pages": [
            {
                "heading": "1. Terms, Factors, Coefficients and Monomials",
                "text": (
                    "Algebraic expressions are formed from variables and constants. Operations of addition, subtraction, "
                    "multiplication, and division are used to combine them. Expressions are made of terms. "
                    "A term is a product of factors. The numerical factor of a term is called its numerical coefficient. "
                    "Terms which have the same algebraic factors are Like Terms (समान पद), while terms with different factors "
                    "are Unlike Terms. Only like terms can be added or subtracted together."
                ),
            },
            {
                "heading": "2. Multiplication and Standard Algebraic Identities",
                "text": (
                    "Multiplying a monomial by a polynomial uses the distributive law: a(b + c) = ab + ac. "
                    "An identity is an equality which is true for all values of the variables in it. "
                    "Standard Identity I: (a + b)^2 = a^2 + 2ab + b^2. This can be visually verified by dividing a large square "
                    "of side (a + b) into two squares of areas a^2 and b^2, and two rectangles each of area ab. "
                    "Standard Identity II: (a - b)^2 = a^2 - 2ab + b^2. "
                    "Standard Identity III: (a + b)(a - b) = a^2 - b^2."
                ),
            },
        ],
    },
    {
        "id": "class6_science_ch02_components_of_food",
        "title": "Components of Food and Balanced Nutrition",
        "filename": "class6_components_of_food.pdf",
        "subject": "science",
        "grade": 6,
        "sim_id": "AVR-P401",
        "sim_name": "Virtual Chemical Reagent Dropper Lab",
        "pages": [
            {
                "heading": "1. Major Nutrients in Food and Chemical Reagent Testing",
                "text": (
                    "The food we eat contains chemical substances necessary for our body's growth, energy, and maintenance, "
                    "called Nutrients (पोषक तत्व). The major nutrients are Carbohydrates, Proteins, Fats, Vitamins, and Minerals. "
                    "In addition, food contains dietary fibres (roughage) and water. "
                    "Carbohydrates and fats provide energy to our body. To test for starch, add 2-3 drops of dilute iodine solution: "
                    "a blue-black color confirms starch presence. To test for protein, add copper sulphate and caustic soda: "
                    "a violet color indicates proteins. Fats leave an oily translucent patch on paper."
                ),
            },
            {
                "heading": "2. Balanced Diet and Deficiency Diseases",
                "text": (
                    "A diet that contains all the essential nutrients in proper amounts, along with adequate water and roughage, "
                    "is called a Balanced Diet (संतुलित आहार). Deficiency of nutrients over a long period leads to diseases or disorders. "
                    "Deficiency of Vitamin A causes night blindness. Deficiency of Vitamin B1 causes Beriberi. "
                    "Deficiency of Vitamin C leads to Scurvy (bleeding gums). Deficiency of Vitamin D causes Rickets. "
                    "Deficiency of Iron causes Anemia, and deficiency of Iodine causes Goiter (swollen thyroid gland)."
                ),
            },
        ],
    },
    {
        "id": "class8_science_ch04_combustion_and_flame",
        "title": "Combustion and Flame — Thermal Zones & Fire Triangle",
        "filename": "class8_combustion_and_flame.pdf",
        "subject": "science",
        "grade": 8,
        "sim_id": "AVR-P311",
        "sim_name": "Particle Temperature Lab & Fire Triangle",
        "pages": [
            {
                "heading": "1. What is Combustion and the Conditions for Fire",
                "text": (
                    "A chemical process in which a substance reacts with oxygen to give off heat is called Combustion (दहन). "
                    "The substance that undergoes combustion is said to be combustible or a fuel. "
                    "For combustion to occur, three conditions must be satisfied simultaneously (The Fire Triangle): "
                    "1. Presence of a combustible substance (fuel). "
                    "2. Presence of a supporter of combustion (oxygen/air). "
                    "3. Attainment of the Ignition Temperature (ज्वलन ताप), which is the lowest temperature at which a substance catches fire. "
                    "Substances with very low ignition temperatures that catch fire easily with a flame are called Inflammable substances."
                ),
            },
            {
                "heading": "2. Controlling Fire and Structure of a Flame",
                "text": (
                    "Fire can be controlled by removing one or more of the requirements: cutting off fuel, blocking air supply, "
                    "or cooling the burning substance below its ignition temperature using water or carbon dioxide extinguishers. "
                    "A flame has three distinct zones: "
                    "1. Outermost non-luminous zone: complete combustion occurs here; it is blue and the hottest part of the flame. "
                    "2. Middle luminous zone: partial combustion occurs; it is yellow, moderately hot, and produces unburnt carbon particles. "
                    "3. Innermost dark zone: contains unburnt wax vapours; it is black and the least hot part."
                ),
            },
        ],
    },
    {
        "id": "class10_science_ch09_heredity_evolution",
        "title": "Heredity and Evolution — Mendelian Genetics & Punnett Squares",
        "filename": "class10_heredity_evolution.pdf",
        "subject": "science",
        "grade": 10,
        "sim_id": "AVR-P321-bio",
        "sim_name": "Mendelian Genetics Punnett Square Simulator",
        "pages": [
            {
                "heading": "1. Inherited Traits and Mendel's Experiments with Garden Peas",
                "text": (
                    "The transmission of characteristics or traits from parents to offspring is called Heredity (आनुवंशिकता). "
                    "Gregor Johann Mendel studied inheritance patterns using the garden pea plant (Pisum sativum) with contrasting traits. "
                    "In a monohybrid cross between a pure tall plant (TT) and a pure dwarf plant (tt), the first filial (F1) generation "
                    "consisted entirely of tall plants (Tt). The trait for tallness is Dominant (प्रभावी), while dwarfness is Recessive (अप्रभावी). "
                    "When F1 plants self-pollinated, the F2 generation exhibited a phenotypic ratio of 3 Tall : 1 Dwarf "
                    "and a genotypic ratio of 1 TT : 2 Tt : 1 tt."
                ),
            },
            {
                "heading": "2. Dihybrid Cross, Independent Assortment and Sex Determination",
                "text": (
                    "In a dihybrid cross involving two pairs of contrasting characters (Round Yellow seeds RRYY vs Wrinkled Green seeds rryy), "
                    "Mendel discovered that traits are inherited independently, producing an F2 phenotypic ratio of 9:3:3:1. "
                    "In human beings, sex is determined genetically through sex chromosomes. Females have two identical X chromosomes (XX), "
                    "while males have one X and one Y chromosome (XY). All children inherit an X chromosome from their mother. "
                    "If the child inherits an X chromosome from the father, it will be a girl; if a Y chromosome is inherited, it will be a boy."
                ),
            },
        ],
    },
]


def create_chapter_pdf(pdf_path: Path, spec: dict) -> None:
    """Create a structured, clean 2-page PDF with authentic text and layout using PyMuPDF."""
    doc = fitz.open()
    for p_idx, page_info in enumerate(spec["pages"], 1):
        page = doc.new_page(width=595, height=842)  # A4 standard
        
        # Header banner
        page.insert_text(
            (50, 60),
            f"NCERT Class {spec['grade']} {spec['subject'].title()} — Chapter Module",
            fontsize=10,
            color=(0.4, 0.4, 0.4),
        )
        page.insert_text(
            (50, 90),
            spec["title"],
            fontsize=16,
            color=(0.1, 0.2, 0.6),
        )
        
        # Section Heading
        page.insert_text(
            (50, 140),
            page_info["heading"],
            fontsize=12,
            color=(0.15, 0.15, 0.15),
        )
        
        # Body text wrapped inside a textbox
        rect = fitz.Rect(50, 160, 545, 650)
        page.insert_textbox(
            rect,
            page_info["text"],
            fontsize=10,
            leading=15,
            color=(0.2, 0.2, 0.2),
        )
        
        # Interactive manipulative callout
        callout_rect = fitz.Rect(50, 670, 545, 750)
        page.draw_rect(callout_rect, color=(0.2, 0.4, 0.8), fill=(0.95, 0.97, 1.0), width=1)
        page.insert_text(
            (60, 695),
            f"Interactive Manipulative: {spec['sim_name']} ({spec['sim_id']})",
            fontsize=10,
            color=(0.1, 0.2, 0.6),
        )
        page.insert_text(
            (60, 720),
            "Hands-on manipulative discovery step integrated before formal formula application.",
            fontsize=9,
            color=(0.3, 0.3, 0.3),
        )
        
        # Footer
        page.insert_text(
            (50, 800),
            f"AASHA AIOS — Page {p_idx} of {len(spec['pages'])} | Standalone Offline Interactive Bundle",
            fontsize=8,
            color=(0.5, 0.5, 0.5),
        )

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(pdf_path))
    doc.close()
    logger.info(f"Generated PDF: {pdf_path} ({pdf_path.stat().st_size} bytes)")


def run_batch_compilation() -> dict:
    """Run sequential, bounded compilation of all 7 target chapters."""
    config = Config.load()
    orch = Orchestrator(config)
    
    staging_dir = PIPELINE_DIR / "staging_pdfs"
    staging_dir.mkdir(parents=True, exist_ok=True)
    
    output_dir = REPO_ROOT / "output" / "chapters"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    aasha_chapters_dir = REPO_ROOT / "Aasha-AI" / "chapters"
    aasha_chapters_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    total_start = time.time()
    
    print("\n" + "=" * 80)
    print(" 🌟 AASHA AIOS — PHASE 2 BATCH CHAPTER SCALING (7 BOTTLENECK CHAPTERS)")
    print("=" * 80 + "\n")
    
    for idx, spec in enumerate(CHAPTERS_SPEC, 1):
        print(f"\n[{idx}/7] Compiling: {spec['title']} (Grade {spec['grade']} {spec['subject']})")
        print(f"      Bound Foundation: {spec['sim_name']} [{spec['sim_id']}]")
        
        pdf_path = staging_dir / spec["filename"]
        create_chapter_pdf(pdf_path, spec)
        
        t0 = time.time()
        try:
            job_id = orch.create_job(
                pdf_path=pdf_path,
                subject=spec["subject"],
                grade=spec["grade"],
                provider="tier0",
                mode="v5-engine",
            )
            
            job = orch.run_pipeline(job_id, max_cost=0.0, mode="v5-engine")
            duration = round(time.time() - t0, 1)
            
            html_src = job.outputs.get("html", "")
            if not html_src or not Path(html_src).is_file():
                # Fallback check in work dir
                work_html = orch.work_root / job_id / "chapter.html"
                if work_html.is_file():
                    html_src = str(work_html)
            
            if html_src and Path(html_src).is_file():
                html_path = Path(html_src)
                html_size = html_path.stat().st_size
                
                # Copy to output/chapters/ with clean canonical name
                dest_output = output_dir / f"{spec['id']}.html"
                shutil.copyfile(str(html_path), str(dest_output))
                
                # Copy to Aasha-AI/chapters/
                dest_aasha = aasha_chapters_dir / f"{spec['id']}.html"
                shutil.copyfile(str(html_path), str(dest_aasha))
                
                res_record = {
                    "index": idx,
                    "id": spec["id"],
                    "title": spec["title"],
                    "grade": spec["grade"],
                    "subject": spec["subject"],
                    "sim_id": spec["sim_id"],
                    "status": "PASS",
                    "duration_s": duration,
                    "size_bytes": html_size,
                    "size_kb": round(html_size / 1024, 1),
                    "output_path": str(dest_output.relative_to(REPO_ROOT)),
                }
                results.append(res_record)
                print(f"      ✓ PASS in {duration}s | Size: {round(html_size/1024, 1)} KB | Cost: $0.0000")
            else:
                print(f"      ✗ FAILED: HTML output not found for job {job_id}")
                results.append({
                    "index": idx,
                    "id": spec["id"],
                    "title": spec["title"],
                    "status": "FAIL",
                    "error": "HTML output not found",
                })
        except Exception as err:
            logger.error(f"Error compiling {spec['id']}: {err}", exc_info=True)
            results.append({
                "index": idx,
                "id": spec["id"],
                "title": spec["title"],
                "status": "ERROR",
                "error": str(err),
            })
            print(f"      ✗ ERROR: {err}")

    total_duration = round(time.time() - total_start, 1)
    
    # Save Batch Manifest Report
    manifest = {
        "manifest_version": "1.0.0",
        "phase": "PHASE_2_BATCH_CHAPTER_SCALING",
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_chapters": len(CHAPTERS_SPEC),
        "passed_chapters": sum(1 for r in results if r.get("status") == "PASS"),
        "total_duration_s": total_duration,
        "total_cost_usd": 0.0,
        "chapters": results,
    }
    
    manifest_file = output_dir / "phase2_batch_manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    
    print("\n" + "=" * 80)
    print(f" BATCH COMPILATION COMPLETE: {manifest['passed_chapters']}/{manifest['total_chapters']} PASSED in {total_duration}s")
    print(f" Manifest saved to: {manifest_file.relative_to(REPO_ROOT)}")
    print("=" * 80 + "\n")
    
    return manifest


if __name__ == "__main__":
    run_batch_compilation()
