/**
 * AASHA F27 Gamified Assessment Adapter + Cycle 2 BilingualFormulaASTValidatorJS & MultiChapterSimStressTesterJS
 */
class BilingualFormulaASTValidatorJS {
  static validateFormula(formula = "") {
    const raw = String(formula).trim();
    if (!raw) throw new Error("FormulaASTValidationError: empty formula");
    const dollars = (raw.match(/\$/g) || []).length;
    if (dollars % 2 !== 0) throw new Error("FormulaASTValidationError: unbalanced $ delimiters");
    let depth = 0;
    for (const ch of raw) {
      if (ch === "{") depth++;
      if (ch === "}") depth--;
      if (depth < 0) throw new Error("FormulaASTValidationError: unbalanced braces");
    }
    if (depth !== 0) throw new Error("FormulaASTValidationError: unclosed braces");
    if (/\\frac\{\s*\}\{|\{\s*\}/.test(raw)) {
      throw new Error("FormulaASTValidationError: empty LaTeX brace group");
    }
    return { valid: true, formula: raw };
  }
}

class MultiChapterSimStressTesterJS {
  static safeDivide(num, den, eps = 1e-9) {
    const safeDen = Math.abs(den) < eps || !Number.isFinite(den) ? (den < 0 ? -eps : eps) : den;
    const val = num / safeDen;
    return Number.isFinite(val) ? Math.max(-1e6, Math.min(1e6, val)) : 0.0;
  }
}

module.exports = {
  BilingualFormulaASTValidatorJS,
  MultiChapterSimStressTesterJS,
};
