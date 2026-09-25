import { tool } from '../tool_mock';
import { z } from 'zod';
import { readFile, writeFile } from 'fs/promises';

export const fileEditTool = tool({
  name: 'file_edit',
  description: 'Apply search-and-replace edits to a file.',
  inputSchema: z.object({
    path: z.string(),
    edits: z.array(z.object({
      old_text: z.string(),
      new_text: z.string()
    }))
  }),
  execute: async ({ path, edits }: { path: string, edits: any[] }) => {
    try {
      let content = await readFile(path, 'utf-8');
      for (const edit of edits) {
        if (!content.includes(edit.old_text)) {
          return `Error: old_text not found exactly in ${path}`;
        }
        content = content.replace(edit.old_text, edit.new_text);
      }
      await writeFile(path, content, 'utf-8');
      return { success: true };
    } catch (err: any) {
      return `Error editing file: ${err.message}`;
    }
  }
});
