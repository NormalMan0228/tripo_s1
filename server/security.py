from fastapi.responses import JSONResponse

class BodyLimitMiddleware:
    """Bound bytes while receiving, including chunked bodies without Content-Length."""
    def __init__(self, app, limit=8192, path_limits=None):
        self.app, self.limit, self.path_limits = app, limit, path_limits or {}

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in ('POST','PUT','PATCH'):
            return await self.app(scope,receive,send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type']=='http.disconnect': return
            size += len(message.get('body',b''))
            if size>self.path_limits.get(scope.get('path'),self.limit):
                return await JSONResponse({'detail':'body_too_large'},413)(scope,receive,send)
            chunks.append(message.get('body',b''))
            if not message.get('more_body',False): break
        delivered = False
        async def bounded_receive():
            nonlocal delivered
            if delivered: return await receive()
            delivered = True
            return {'type':'http.request','body':b''.join(chunks),'more_body':False}
        await self.app(scope,bounded_receive,send)
