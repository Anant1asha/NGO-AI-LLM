import { tool } from '../tool_mock';
import { z } from 'zod';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const shellTool = tool({
  name: 'shell',
  description: 'Execute shell commands.',
  inputSchema: z.object({
    command: z.string().describe('Command to run')
  }),
  execute: async ({ command }: { command: string }) => {
    try {
      const { stdout, stderr } = await execAsync(command);
      return { stdout, stderr };
    } catch (err: any) {
      return { error: err.message, stdout: err.stdout, stderr: err.stderr };
    }
  }
});
