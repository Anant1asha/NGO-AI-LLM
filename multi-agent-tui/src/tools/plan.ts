import { tool } from '../tool_mock';
import { z } from 'zod';

let currentPlan = '';

export const planTool = tool({
  name: 'plan',
  description: 'Manage the current plan/todo list.',
  inputSchema: z.object({
    action: z.enum(['get', 'set', 'append']),
    content: z.string().optional()
  }),
  execute: async ({ action, content }: { action: string; content?: string }) => {
    if (action === 'get') return currentPlan;
    if (action === 'set' && content) {
      currentPlan = content;
      return 'Plan updated.';
    }
    if (action === 'append' && content) {
      currentPlan += '\n' + content;
      return 'Plan appended.';
    }
    return 'Invalid action.';
  }
});
