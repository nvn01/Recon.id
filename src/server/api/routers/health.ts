import { createTRPCRouter, publicProcedure } from "~/server/api/trpc";

export const healthRouter = createTRPCRouter({
  status: publicProcedure.query(() => {
    return {
      ok: true,
      phase: "backend-api",
    };
  }),
});
