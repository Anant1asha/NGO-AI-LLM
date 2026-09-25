import { tool } from '../tool_mock';
import { z } from 'zod';
import { runAgent } from '../agent'; // We'll export runAgent from agent.ts

export const subAgentTool = tool({
  name: 'sub_agent',
  description: 'Delegate a task to a specialized sub-agent (e.g. Researcher, Coder, Reviewer).',
  inputSchema: z.object({
    role: z.enum(['Researcher', 'Coder', 'Reviewer']).describe('The persona of the sub-agent'),
    task: z.string().describe('The task for the sub-agent to perform')
  }),
  execute: async ({ role, task }: { role: string; task: string }) => {
    try {
      console.log(`\n[Orchestrator] Delegating to ${role} sub-agent...`);
      // We will define specific tools based on the role inside agent.ts or here.
      const result = await runAgent(task, role);
      return result;
    } catch (err: any) {
      return `Sub-agent failed: ${err.message}`;
    }
  }
});
