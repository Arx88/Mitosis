import { createClient } from './supabase/client';

// Initialize Supabase client internally - NOT USED BY supabaseClient.execute
const supabase = createClient();
const API_PREFIX = process.env.NEXT_PUBLIC_API_PREFIX || '/api';

// ---- Interfaces for initiateAndStreamAgent ----
export interface InitiateAgentPayload {
	prompt: string;
	model_name?: string;
	enable_thinking?: boolean;
	reasoning_effort?: string;
	enable_context_manager?: boolean;
	agent_id?: string;
	files?: FileList | File[];
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

// ---- initiateAndStreamAgent function ----
export function initiateAndStreamAgent(
	payload: InitiateAgentPayload,
	handlers: StreamHandlers
): { close: () => void } {
	const abortController = new AbortController();
	const { signal } = abortController;

	const executeStream = async () => { // Renamed from execute to avoid conflict if any
		console.log('Executing initiateAndStreamAgent');
		try {
			const sessionResponse = await supabase.auth.getSession(); // Uses the local supabase instance
			const token = sessionResponse?.data?.session?.access_token;

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
					if (buffer.startsWith('data: ')) {
						const jsonString = buffer.substring('data: '.length).trim();
						if (jsonString) {
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
					} else if (buffer.trim()) {
						console.warn('Received non-SSE data at stream end:', buffer);
					}
					break;
				}

				buffer += decoder.decode(value, { stream: true });
				const messages = buffer.split('\n\n');

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
					} else if (msg.trim()) {
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

	executeStream();

	return {
		close: () => {
			abortController.abort();
		}
	};
}

// ---- Standard API Response Structure for backendApi ----
export interface ApiResponse<T> {
    data: T | null;
    error: Error | null;
    success: boolean;
}

// ---- backendApi Implementation ----
export const backendApi = {
    get: async <T>(
        path: string,
        options?: { headers?: Record<string, string>; [key: string]: any; }
    ): Promise<ApiResponse<T>> => {
        try {
            const sessionResponse = await supabase.auth.getSession(); // Uses the local supabase instance
            const token = sessionResponse?.data?.session?.access_token;

            const mergedHeaders: Record<string, string> = {
                ...options?.headers, // Spread custom headers from options
            };

            if (token) {
                mergedHeaders['Authorization'] = `Bearer ${token}`; // Add/override Authorization header
            }

            const response = await fetch(`${API_PREFIX}${path}`, {
                method: 'GET',
                headers: mergedHeaders,
            });

            if (!response.ok) {
                const errorText = await response.text().catch(() => `HTTP error ${response.status}`);
                return { data: null, error: new Error(errorText || `HTTP error ${response.status}`), success: false };
            }

            if (response.status === 204 || response.headers.get('content-length') === '0') {
                return { data: null, error: null, success: true };
            }

            const responseData: T = await response.json();
            return { data: responseData, error: null, success: true };
        } catch (error) {
            return { data: null, error: error instanceof Error ? error : new Error(String(error)), success: false };
        }
    },

    post: async <T>(
        path: string,
        body: any,
        options?: { headers?: Record<string, string>; [key: string]: any; }
    ): Promise<ApiResponse<T>> => {
        try {
            const sessionResponse = await supabase.auth.getSession(); // Uses the local supabase instance
            const token = sessionResponse?.data?.session?.access_token;

            const mergedHeaders: Record<string, string> = {
                'Content-Type': 'application/json', // Default Content-Type
                ...options?.headers, // Spread custom headers from options
            };

            if (token) {
                mergedHeaders['Authorization'] = `Bearer ${token}`; // Add/override Authorization header
            }

            const response = await fetch(`${API_PREFIX}${path}`, {
                method: 'POST',
                headers: mergedHeaders,
                body: JSON.stringify(body),
            });

            if (!response.ok) {
                const errorText = await response.text().catch(() => `HTTP error ${response.status}`);
                return { data: null, error: new Error(errorText || `HTTP error ${response.status}`), success: false };
            }

            if (response.status === 204 || response.headers.get('content-length') === '0') {
                return { data: null, error: null, success: true };
            }

            const contentType = response.headers.get("content-type");
            if (contentType && contentType.indexOf("application/json") !== -1) {
                const responseData: T = await response.json();
                return { data: responseData, error: null, success: true };
            } else {
                return { data: null, error: null, success: true };
            }

        } catch (error) {
            return { data: null, error: error instanceof Error ? error : new Error(String(error)), success: false };
        }
    },
};

// ---- supabaseClient.execute wrapper ----

export interface ExecuteContext {
    operation: string;
    resource?: string;
    showErrors?: boolean; // Not directly used by this execute, but could be by a global error handler
    silent?: boolean;
}

export interface ExecuteResponse<T> {
    data: T | null;
    error: Error | null;
    success: boolean;
    status?: number;
    originalError?: any;
}

export const supabaseClient = {
    execute: async <T>(
        asyncFn: () => Promise<{ data: T | null; error: any }>,
        context?: ExecuteContext
    ): Promise<ExecuteResponse<T>> => {
        const operation = context?.operation || 'Unknown operation';
        const resource = context?.resource || 'N/A';
        const silent = context?.silent || false;

        if (!silent) {
            console.log(`[DB Operation: ${operation}] Starting for resource: ${resource}`);
        }

        try {
            const result = await asyncFn();

            if (result.error) {
                let errorMessage = `Error in ${operation} for resource ${resource}: ${result.error.message || 'Unknown error'}`;
                if (result.error.details) errorMessage += ` Details: ${result.error.details}`;
                if (result.error.hint) errorMessage += ` Hint: ${result.error.hint}`;
                if (result.error.code) errorMessage += ` Code: ${result.error.code}`;

                if (!silent) {
                    console.error(`[DB Operation: ${operation}] Failed for resource ${resource}:`, errorMessage, result.error);
                }

                return {
                    data: null,
                    error: new Error(errorMessage),
                    success: false,
                    originalError: result.error,
                    status: result.error.status || (result.error.code ? parseInt(result.error.code, 10) : undefined) || undefined,
                };
            }

            if (!silent) {
                console.log(`[DB Operation: ${operation}] Succeeded for resource: ${resource}`);
            }
            return { data: result.data, error: null, success: true };

        } catch (e) {
            const caughtError = e instanceof Error ? e : new Error(String(e));
            if (!silent) {
                console.error(`[DB Operation: ${operation}] Exception for resource ${resource}:`, caughtError);
            }
            return { data: null, error: caughtError, success: false };
        }
    },
};
