import jwt
import datetime


def create_jwt_token(user_id: str, secret: str, expiration_time: int, algorithm: str) -> str:

    payload = {
        'user_id': user_id,
        'type': 'access',
        'exp': datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=expiration_time)
    }
    token = jwt.encode(payload, secret, algorithm=algorithm)
    return token


def create_refresh_jwt_token(user_id: str, refresh_secret: str, refresh_expiration_time: int, refresh_algorithm: str) -> str:
    payload = {
        'user_id': user_id,
        'type': 'refresh',
        'exp': datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=refresh_expiration_time)
    }
    refresh_token = jwt.encode(payload, refresh_secret, algorithm=refresh_algorithm)
    return refresh_token

def decode_jwt_token(token: str, secret: str, algorithm: str) -> dict:

    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        if 'user_id' not in payload:
            raise Exception("400 Invalid token: user_id not found")
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception("400 Token has expired")
    except jwt.InvalidTokenError:
        raise Exception("400 Invalid token")


def refresh_jwt_token(
    refresh_token: str,
    refresh_secret: str,
    access_secret: str,
    access_expiration_time: int,
    refresh_algorithm: str,
    access_algorithm: str,
) -> str:
    try:
        payload = jwt.decode(refresh_token, refresh_secret, algorithms=[refresh_algorithm])
        user_id = payload['user_id']
        new_token = create_jwt_token(user_id, access_secret, access_expiration_time, access_algorithm)
        return new_token
    except jwt.ExpiredSignatureError:
        raise Exception("400 Refresh token has expired")
    except jwt.InvalidTokenError:
        raise Exception("400 Invalid refresh token")

