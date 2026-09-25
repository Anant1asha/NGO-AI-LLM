import { z } from 'zod';

export function tool<T extends z.ZodTypeAny>(params: {
  name: string;
  description: string;
  inputSchema: T;
  execute: (args: z.infer<T>) => Promise<any>;
}) {
  return params;
}
