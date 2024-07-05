from joserfc import jwt
from joserfc.errors import JoseError
from fastapi import Request
import redis.asyncio as redis
import json

REDIS_TTL = 259200  # 3 дня

COOKIE_AUTH = 'auth-token'
REDIS_KEY_USER_REGISTER = "user_register"


class RedisTokenManager(redis.Redis):
    def __init__(self, *args, jwt_secret_key: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.jwt_secret_key = jwt_secret_key

    async def set_token(self, user_id, device_id, response=None, telegram=False):
        key = 't' if telegram else 'k'
        token = jwt.encode({'alg': 'HS256'},
                           {key: user_id, 'd': device_id},
                           self.jwt_secret_key)
        await self.set(f"{COOKIE_AUTH}:{key}:{user_id}:{device_id}", token, ex=REDIS_TTL)
        if response:
            response.set_cookie(key=COOKIE_AUTH, value=token, max_age=REDIS_TTL)
        return token

    # стоит продумать польностью логику, чтобы использовать tgid локально при регистрации,
    #  но тогда усложняется мидлварь и лишние проверки, а ценности пока мало
    async def check_token(self, token: [str | Request]):
        if isinstance(token, Request):
            token = token.cookies.get(COOKIE_AUTH)
        if not token:
            return None, None
        try:
            token_parts = jwt.decode(token, self.jwt_secret_key)
            key = 't' if token_parts.claims.get('t') else "k"
            user_id = token_parts.claims[key]
            device_id = token_parts.claims['d']
        except JoseError:
            return None, None
        except Exception as e:
            print("Error: check_token exception:", e)
            return None, None
        stored_token = await self.get(f"{COOKIE_AUTH}:{key}:{user_id}:{device_id}")
        if isinstance(stored_token, bytes):
            stored_token = stored_token.decode('utf-8')
        if not stored_token or stored_token != token:
            return None, None

        return user_id, device_id

    async def delete_token(self, user_id, device_id):
        await self.delete(f"{COOKIE_AUTH}:{user_id}:{device_id}")

    async def set_register_data(self, user_id, session_data):
        await self.set(f"{REDIS_KEY_USER_REGISTER}:{user_id}", json.dumps(session_data), ex=REDIS_TTL)
