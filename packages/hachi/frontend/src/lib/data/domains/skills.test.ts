// Regression test for BB-34: duplicate skill names → duplicate React keys →
// React warning "Encountered two children with the same key".
//
// Root cause: get_skill_inventory() iterates _nodes (keyed by qid); two nodes
// with the same name (e.g. "identity") produce duplicate rows. The frontend
// adapter sets id = raw.name, so duplicate names → duplicate React keys.
//
// Fix: deduplicateSkillsByName() in skills.ts filters the raw list before mapping.

import { describe, it, expect } from 'vitest'
import { deduplicateSkillsByName } from './skills'

type RawSkill = { name: string; role: string; keyword_count: number; use_count: number; last_used: string | null }

describe('deduplicateSkillsByName (BB-34)', () => {
  it('removes the second of two skills with the same name', () => {
    const raw: RawSkill[] = [
      { name: 'identity', role: 'r1', keyword_count: 3, use_count: 5, last_used: null },
      { name: 'identity', role: 'r2', keyword_count: 1, use_count: 2, last_used: null },
      { name: 'other', role: 'r3', keyword_count: 2, use_count: 1, last_used: null },
    ]
    const result = deduplicateSkillsByName(raw)
    expect(result).toHaveLength(2)
    expect(result.map((s) => s.name)).toEqual(['identity', 'other'])
  })

  it('keeps the first occurrence (highest use_count when pre-sorted)', () => {
    const raw: RawSkill[] = [
      { name: 'alpha', role: 'r1', keyword_count: 1, use_count: 10, last_used: null },
      { name: 'alpha', role: 'r2', keyword_count: 1, use_count: 1, last_used: null },
    ]
    const result = deduplicateSkillsByName(raw)
    expect(result).toHaveLength(1)
    expect(result[0].use_count).toBe(10)
  })

  it('passes through a list with no duplicates unchanged', () => {
    const raw: RawSkill[] = [
      { name: 'a', role: '', keyword_count: 0, use_count: 0, last_used: null },
      { name: 'b', role: '', keyword_count: 0, use_count: 0, last_used: null },
    ]
    expect(deduplicateSkillsByName(raw)).toHaveLength(2)
  })

  it('handles an empty list', () => {
    expect(deduplicateSkillsByName([])).toEqual([])
  })
})
