import { client } from './client';
import type {
	AddSkillRequest,
	DirectoryListing,
	DownloadTokenResponse,
	MCPClient,
	MCPClientStatus,
	Skill,
} from './types';

export const workspaceApi = {
	directories: (agentId: string, sessionId: string, path = '') =>
		client.get<DirectoryListing>('/workspace/directories', {
			agent_id: agentId,
			session_id: sessionId,
			path,
		}),

	readFile: (agentId: string, sessionId: string, path: string, download = false) =>
		client.stream('/workspace/files', {
			method: 'GET',
			params: {
				agent_id: agentId,
				session_id: sessionId,
				path,
				download: String(download),
			},
		}),

	downloadToken: (agentId: string, sessionId: string, path: string) =>
		client.post<DownloadTokenResponse>('/workspace/files/download-token', null, {
			agent_id: agentId,
			session_id: sessionId,
			path,
		}),

	mcp: {
		list: (agentId: string, sessionId: string) =>
			client.get<MCPClientStatus[]>('/workspace/mcp', {
				agent_id: agentId,
				session_id: sessionId,
			}),

		add: (agentId: string, sessionId: string, mcp: MCPClient) =>
			client.post<void>('/workspace/mcp', mcp, { agent_id: agentId, session_id: sessionId }),

		remove: (mcpName: string, agentId: string, sessionId: string) =>
			client.delete(`/workspace/mcp/${mcpName}`, {
				agent_id: agentId,
				session_id: sessionId,
			}),
	},

	skill: {
		list: (agentId: string, sessionId: string) =>
			client.get<Skill[]>('/workspace/skill', { agent_id: agentId, session_id: sessionId }),

		add: (agentId: string, sessionId: string, body: AddSkillRequest) =>
			client.post<void>('/workspace/skill', body, {
				agent_id: agentId,
				session_id: sessionId,
			}),

		remove: (skillName: string, agentId: string, sessionId: string) =>
			client.delete(`/workspace/skill/${skillName}`, {
				agent_id: agentId,
				session_id: sessionId,
			}),
	},
};
