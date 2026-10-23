export const state = {session: null, tenantId: null, context: null};
export const podeEscrever = () => Boolean(state.context?.permissions?.includes('write'));
