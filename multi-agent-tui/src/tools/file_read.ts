import { tool } from '../tool_mock';
import { z } from 'zod';
import { readFile } from 'fs/promises';

export const fileReadTool = tool({
  name: 'file_read',
  description: 'Read the contents of a file.',
  inputSchema: z.object({
    path: z.string().describe('Absolute path to the file')
  }),
  execute: async ({ path }: { path: string }) => {
    try {
      const content = await readFile(path, 'utf-8');
      return content;
    } catch (err: any) {
      return `Error reading file: ${err.message}`;
    }
  }
});
