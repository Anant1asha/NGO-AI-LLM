# Conventions & Invariants

1. **Zero-Token Bleed**: Never chain fallbacks into paid Gemini keys. Always use Tier 1 OpenRouter free models or Tier 2 Claude Code.
2. **Mathematical Insulation**: Shield all LaTeX math (`\( ... \)`, `$$ ... $$`, `$...$`) and single-letter variables via `__AASHA_MATH_X__` before applying bilingual dictionary wrapping (`rt()` / `window.WM`).
3. **Symbolic Operations First**: In Serena, use AST/symbolic tools (`find_symbol`, `get_symbols_overview`, `replace_symbol_body`, `rename_symbol`) over raw line replacements whenever manipulating classes or methods.
4. **Zero-Spoiler Assessment**: Misconception diagnostics (`m`) and 4-tier progressive hints (`H1` to `H4`) must never leak answers or verbatim calculations evaluating to target values.
5. **Responsiveness**: Concept cards and `<aasha-sim>` canvas viewports must fit within mobile viewports without vertical scroll (`scrollH <= winH + 5`). Minimum touch target 44x44px.
