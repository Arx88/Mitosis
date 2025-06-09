import { getSupabaseClient } from './supabase/client'; // Changed import
// Removed: import { PUBLIC_API_PREFIX } from '$env/static/public';

const supabase = getSupabaseClient(); // Call the function to get the client
const API_PREFIX = process.env.NEXT_PUBLIC_API_PREFIX || '/api'; // Redefined API_PREFIX

export interface InitiateAgentPayload {
	prompt: string;
	model_name?: string;
	enable_thinking?: boolean;
	reasoning_effort?: string;
	enable_context_manager?: boolean;
	agent_id?: string;
	files?: FileList | File[]; // Accept FileList or File[]
	is_agent_builder?: boolean;
	target_agent_id?: string;
}

export type StreamEventType = 'thought' | 'tool_call' | 'tool_result' | 'final_response' | 'error';

export interface StreamEvent {
	type: StreamEventType;
	content?: any;
	tool_name?: string;
	tool_args?: Record<string, any>;
	tool_output?: any;
	is_error?: boolean;
	message?: string;
}

export interface StreamHandlers {
	onOpen?: () => void;
	onMessage: (event: StreamEvent) => void;
	onError?: (error: Error) => void;
	onClose?: () => void;
}

export function initiateAndStreamAgent(
	payload: InitiateAgentPayload,
	handlers: StreamHandlers
): { close: () => void } {
	const abortController = new AbortController();
	const { signal } = abortController;

	const execute = async () => {
		console.log('Executing initiateAndStreamAgent'); // Added log
		try {
			const session = await supabase.auth.getSession();
			const token = session?.data?.session?.access_token;

			if (!token) {
				throw new Error('Authentication token not available.');
			}

			const formData = new FormData();
			formData.append('prompt', payload.prompt);
			formData.append('stream', 'true');

			if (payload.model_name) formData.append('model_name', payload.model_name);
			if (payload.enable_thinking !== undefined)
				formData.append('enable_thinking', String(payload.enable_thinking));
			if (payload.reasoning_effort)
				formData.append('reasoning_effort', payload.reasoning_effort);
			if (payload.enable_context_manager !== undefined)
				formData.append('enable_context_manager', String(payload.enable_context_manager));
			if (payload.agent_id) formData.append('agent_id', payload.agent_id);
			if (payload.is_agent_builder !== undefined)
				formData.append('is_agent_builder', String(payload.is_agent_builder));
			if (payload.target_agent_id)
				formData.append('target_agent_id', payload.target_agent_id);

			if (payload.files) {
                // Ensure payload.files is an array before iterating
                const filesArray = Array.isArray(payload.files) ? payload.files : Array.from(payload.files);
				for (const file of filesArray) {
					formData.append('files', file);
				}
			}

			const response = await fetch(`${API_PREFIX}/agent/initiate`, {
				method: 'POST',
				headers: {
					Authorization: `Bearer ${token}`
				},
				body: formData,
				signal
			});

			if (!response.ok) {
				const errorBody = await response.json().catch(() => ({ detail: response.statusText }));
				throw new Error(
					`HTTP error ${response.status}: ${errorBody.detail || 'Failed to start agent'}`
				);
			}

			if (handlers.onOpen) {
				handlers.onOpen();
			}

			if (!response.body) {
				throw new Error('Response body is null');
			}

			const reader = response.body.getReader();
			const decoder = new TextDecoder();
			let buffer = '';

			while (true) {
				const { done, value } = await reader.read();
				if (done) {
					// Process any remaining data in the buffer when the stream is done
					if (buffer.startsWith('data: ')) {
						const jsonString = buffer.substring('data: '.length).trim();
						if (jsonString) { // Ensure there's content after "data: "
							try {
								const eventData = JSON.parse(jsonString);
								handlers.onMessage(eventData as StreamEvent);
							} catch (e) {
								console.error('Failed to parse final SSE event data fragment:', jsonString, e);
								if (handlers.onError) {
									handlers.onError(new Error(`Failed to parse final SSE event fragment: ${jsonString}`));
								}
							}
						}
					} else if (buffer.trim()) { // If it's not empty and doesn't start with "data: "
						console.warn('Received non-SSE data at stream end:', buffer);
					}
					break;
				}

				buffer += decoder.decode(value, { stream: true });
				const messages = buffer.split('\n\n');

				// The last part of the split is potentially an incomplete message, so keep it in buffer.
				// All other parts are complete messages.
				buffer = messages.pop() || '';

				for (const msg of messages) {
					if (msg.startsWith('data: ')) {
						const jsonString = msg.substring('data: '.length);
						try {
							const eventData = JSON.parse(jsonString);
							handlers.onMessage(eventData as StreamEvent);
						} catch (e) {
							console.error('Failed to parse SSE event data:', jsonString, e);
							if (handlers.onError) {
								handlers.onError(new Error(`Failed to parse SSE event: ${jsonString}`));
							}
						}
					} else if (msg.trim()) { // Log if we receive a non-empty message not starting with "data: "
                        console.warn('Received message not in SSE format:', msg);
                    }
				}
			}
		} catch (error) {
			if (signal.aborted) {
				console.log('Stream aborted by client.');
			} else if (handlers.onError) {
				handlers.onError(error instanceof Error ? error : new Error(String(error)));
			} else {
				console.error('Unhandled stream error:', error);
			}
		} finally {
			if (handlers.onClose) {
				handlers.onClose();
			}
		}
	};

	execute();

	return {
		close: () => {
			abortController.abort();
		}
	};
}

// Example of how to use other API functions (if any) - placeholder
export async function getSomeData(): Promise<any> {
	const session = await supabase.auth.getSession();
	const token = session?.data?.session?.access_token;
	if (!token) throw new Error('Not authenticated');

	const response = await fetch(`${API_PREFIX}/some-data-route`, {
		headers: {
			Authorization: `Bearer ${token}`
		}
	});
	if (!response.ok) throw new Error('Failed to fetch data');
	return response.json();
}
