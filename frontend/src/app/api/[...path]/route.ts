import { NextRequest } from 'next/server';

const BACKEND_API_BASE = process.env.BACKEND_API_BASE ?? 'http://127.0.0.1:8001';

function buildBackendUrl(pathSegments: string[], request: NextRequest): string {
  const backendUrl = new URL(`${BACKEND_API_BASE}/${pathSegments.join('/')}`);
  backendUrl.search = request.nextUrl.search;
  return backendUrl.toString();
}

async function proxyRequest(request: NextRequest, pathSegments: string[]): Promise<Response> {
  const targetUrl = buildBackendUrl(pathSegments, request);
  const headers = new Headers(request.headers);
  headers.delete('host');
  headers.delete('connection');
  headers.delete('content-length');

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: 'manual',
  };

  if (request.method !== 'GET' && request.method !== 'HEAD') {
    init.body = await request.arrayBuffer();
  }

  const backendResponse = await fetch(targetUrl, init);
  const responseHeaders = new Headers(backendResponse.headers);
  responseHeaders.delete('content-encoding');
  responseHeaders.delete('transfer-encoding');

  return new Response(backendResponse.body, {
    status: backendResponse.status,
    statusText: backendResponse.statusText,
    headers: responseHeaders,
  });
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<Response> {
  const { path } = await context.params;
  return proxyRequest(request, path);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<Response> {
  const { path } = await context.params;
  return proxyRequest(request, path);
}
