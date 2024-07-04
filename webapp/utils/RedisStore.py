from joserfc import jwt
from joserfc.errors import JoseError
from fastapi import Request
import redis.asyncio as redis

COOKIE_AUTH = 'auth-token'
REDIS_TTL = 259200  # 3 дня


class RedisTokenManager(redis.Redis):

    def __init__(self, *args, jwt_secret_key: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.jwt_secret_key = jwt_secret_key

    async def set_token(self, user_id, device_id, response=None):
        token = jwt.encode({'alg': 'HS256'}, {'k': user_id, 'd': device_id}, self.jwt_secret_key)
        await self.set(f"{COOKIE_AUTH}:{user_id}:{device_id}", token, ex=REDIS_TTL)
        if response:
            response.set_cookie(key=COOKIE_AUTH, value=token, max_age=REDIS_TTL)
        return token

    async def check_token(self, token: [str | Request]):
        if isinstance(token, Request):
            token = token.cookies.get(COOKIE_AUTH)
        if not token:
            return None, None
        try:
            token_parts = jwt.decode(token, self.jwt_secret_key)
        except JoseError:
            return None, None
        user_id = token_parts.claims['k']
        device_id = token_parts.claims['d']
        stored_token = await self.get(f"{COOKIE_AUTH}:{user_id}:{device_id}")
        if not stored_token or stored_token.decode('utf-8') != token:
            return None, None

        return user_id, device_id

    async def delete_token(self, user_id, device_id):
        await self.delete(f"{COOKIE_AUTH}:{user_id}:{device_id}")
