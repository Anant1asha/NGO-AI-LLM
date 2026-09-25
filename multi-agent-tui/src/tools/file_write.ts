import { tool } from '../tool_mock';
import { z } from 'zod';
import { writeFile, mkdir } from 'fs/promises';
import { dirname } from 'path';

export const fileWriteTool = tool({
  name: 'file_write',
  description: 'Write content to a file.',
  inputSchema: z.object({
    path: z.string().describe('Absolute path to the file'),
    content: z.string().describe('Content to write')
  }),
  execute: async ({ path, content }: { path: string; content: string }) => {
    try {
      await mkdir(dirname(path), { recursive: true });
      await writeFile(path, content, 'utf-8');
      return { written: true, path };
    } catch (err: any) {
      return `Error writing file: ${err.message}`;
    }
  }
});
