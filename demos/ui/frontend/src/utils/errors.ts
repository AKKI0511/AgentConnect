export class BaseError extends Error {
  constructor(message: string, public code: string) {
    super(message);
    this.name = this.constructor.name;
  }
}

export class ApiError extends BaseError {
  constructor(
    message: string,
    public status: number,
    code = 'API_ERROR'
  ) {
    super(message, code);
  }
}

export class WebSocketError extends BaseError {
  constructor(
    message: string,
    public event?: Event,
    code = 'WEBSOCKET_ERROR'
  ) {
    super(message, code);
  }
}

export class AuthError extends BaseError {
  constructor(
    message: string,
    code = 'AUTH_ERROR'
  ) {
    super(message, code);
  }
}

export const isApiError = (error: unknown): error is ApiError => {
  return error instanceof ApiError;
};

export const isWebSocketError = (error: unknown): error is WebSocketError => {
  return error instanceof WebSocketError;
};

export const isAuthError = (error: unknown): error is AuthError => {
  return error instanceof AuthError;
}; 