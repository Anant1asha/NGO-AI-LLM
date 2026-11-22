// Regression test for T4 — Terminal streaming prop controls caret visibility (BB-80)
import { describe, it, expect, afterEach } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { Terminal } from './Terminal';

afterEach(cleanup);

describe('Terminal — streaming prop controls caret (BB-80)', () => {
  it('caret is present when streaming=true (default)', () => {
    const { container } = render(<Terminal lines={[]} />);
    expect(container.querySelector('.hachi-caret')).not.toBeNull();
  });

  it('caret is absent when streaming=false', () => {
    const { container } = render(<Terminal lines={[]} streaming={false} />);
    expect(container.querySelector('.hachi-caret')).toBeNull();
  });
});
