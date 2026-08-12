import { client } from './client';

export interface HealthResponse {
	status: 'ok';
}

export const healthApi = {
	get: () => client.get<HealthResponse>('/health'),
};
