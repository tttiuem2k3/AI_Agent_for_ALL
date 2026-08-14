import { getBaseUrl, getUserId } from './client';

export interface DocumentConversionHealth {
	ok: boolean;
	native_version?: string | null;
	python?: string;
	message?: string;
}

export interface DocumentConversionResult {
	ok: true;
	filename: string;
	format: string;
	markdown: string;
	warnings: string[];
	elapsed_ms: number;
	input_bytes: number;
	markdown_chars: number;
	native_version: string | null;
}

interface FastApiFailure {
	detail?: unknown;
}

function serviceUrl(path: string): string {
	return new URL(path, getBaseUrl()).toString();
}
async function parseResponse<T>(response: Response): Promise<T> {
	const payload = (await response.json()) as T | FastApiFailure;
	if (!response.ok) {
		const detail = (payload as FastApiFailure).detail;
		const message =
			typeof detail === 'string'
				? detail
				: detail !== undefined
					? JSON.stringify(detail)
					: response.statusText;
		throw new Error(message);
	}
	return payload as T;
}

function userHeaders(): Record<string, string> {
	return { 'X-User-ID': getUserId() };
}

export const documentConversionApi = {
	health: async () => {
		const response = await fetch(serviceUrl('/document-conversion/health'), {
			headers: userHeaders(),
		});
		return parseResponse<DocumentConversionHealth>(response);
	},
	convert: async (file: File) => {
		const response = await fetch(serviceUrl('/document-conversion/convert'), {
			method: 'POST',
			headers: {
				...userHeaders(),
				'Content-Type': 'application/octet-stream',
				'X-File-Name': encodeURIComponent(file.name),
			},
			body: file,
		});
		return parseResponse<DocumentConversionResult>(response);
	},
};
