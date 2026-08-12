import { client } from './client';
import type {
	AgentEvent,
	CreateSessionRequest,
	CreateSessionResponse,
	InterruptSessionResponse,
	SessionListResponse,
	SessionStatusResponse,
	SessionRecord,
	UpdateSessionRequest,
	Msg,
} from './types';

export interface MessagesResponse {
	messages: Msg[];
	is_running: boolean;
	has_more: boolean;
	next_before: string | null;
}

type SessionIdentity =
	| { agent_id: string; runtime_subject_id?: never }
	| { agent_id?: never; runtime_subject_id: string };

function identityParams(identity: string | SessionIdentity): Record<string, string> {
	if (typeof identity === 'string') return { agent_id: identity };
	const agentId = identity.agent_id;
	if (agentId) return { agent_id: agentId };
	const runtimeSubjectId = identity.runtime_subject_id;
	if (runtimeSubjectId) return { runtime_subject_id: runtimeSubjectId };
	throw new Error('Session identity requires agent_id or runtime_subject_id');
}

export const sessionApi = {
	list: (agentId: string) => client.get<SessionListResponse>('/sessions/', { agent_id: agentId }),

	create: (body: CreateSessionRequest) => client.post<CreateSessionResponse>('/sessions/', body),

	update: (sessionId: string, agentId: string, body: UpdateSessionRequest) =>
		client.patch<SessionRecord>(`/sessions/${sessionId}`, body, { agent_id: agentId }),

	delete: (sessionId: string, agentId: string) =>
		client.delete(`/sessions/${sessionId}`, { agent_id: agentId }),

	interrupt: (sessionId: string, identity: string | SessionIdentity) =>
		client.post<InterruptSessionResponse>(
			`/sessions/${sessionId}/interrupt`,
			null,
			identityParams(identity),
		),

	status: (sessionId: string, identity: string | SessionIdentity) =>
		client.get<SessionStatusResponse>(
			`/sessions/${sessionId}/status`,
			identityParams(identity),
		),

	messages: (
		sessionId: string,
		agentId: string,
		offset?: number,
		limit = 50,
		before?: string,
	) => {
		const params: Record<string, string> = {
			agent_id: agentId,
			limit: String(limit),
		};
		if (offset !== undefined) params.offset = String(offset);
		if (before) params.before = before;
		return client.get<MessagesResponse>('/sessions/' + sessionId + '/messages', params);
	},

	/**
	 * Subscribe to a session's live event stream via SSE.
	 *
	 * Opens a long-lived ``GET /sessions/{sid}/stream`` connection and
	 * yields each ``AgentEvent`` as it arrives. The connection stays
	 * open until the caller aborts via the ``signal`` or closes the
	 * generator.
	 *
	 * Uses fetch-based SSE (not native ``EventSource``) so the
	 * ``X-User-ID`` custom header is sent.
	 *
	 * @param sessionId - The session to subscribe to.
	 * @param agentId - The agent that owns the session.
	 * @param signal - Optional abort signal to close the connection.
	 * @returns An async generator yielding ``AgentEvent`` objects.
	 */
	streamEvents: async function* (
		sessionId: string,
		agentId: string,
		signal?: AbortSignal,
	): AsyncGenerator<AgentEvent> {
		const res = await client.stream(`/sessions/${sessionId}/stream`, {
			method: 'GET',
			params: { agent_id: agentId },
			signal,
		});

		const reader = res.body!.getReader();
		const decoder = new TextDecoder();
		let buffer = '';

		try {
			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() ?? '';

				for (const line of lines) {
					if (line.startsWith('data: ')) {
						const json = line.slice(6).trim();
						if (json) yield JSON.parse(json) as AgentEvent;
					}
					// SSE comment frames (`:...\n`) are silently skipped
					// (used for heartbeats).
				}
			}
		} finally {
			reader.releaseLock();
		}
	},
};
