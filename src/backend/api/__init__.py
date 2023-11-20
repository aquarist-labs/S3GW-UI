# Copyright 2023 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pyright: reportUnnecessaryCast=false

import contextlib
import re
from typing import Annotated, Any, AsyncGenerator, Dict, Literal, Tuple, cast

import boto3.utils
import pydash
from aiobotocore.session import AioSession
from botocore.config import Config as S3Config
from botocore.exceptions import ClientError, EndpointConnectionError, SSLError
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.logger import logger
from types_aiobotocore_s3.client import S3Client

from backend.config import Config


class S3GWClient:
    """
    Represents the client connection to the s3gw server.

    A connection is not opened by this class. Instead, a client is created when
    requesting a connection via the `conn()` context manager, and the connection
    is handled by the `aiobotocore's S3Client` class that is returned.
    """

    _endpoint: str
    _access_key: str
    _secret_key: str

    def __init__(
        self, config: Config, access_key: str, secret_key: str
    ) -> None:
        """
        Creates a new `S3GWClient` instance.

        Arguments:
        * `endpoint`: the URL where the server is expected to be at.
        * `access_key`: the user's `access key`.
        * `secret_key`: the user's `secret access key`.
        """
        self._config = config
        self._access_key = access_key
        self._secret_key = secret_key

    @property
    def endpoint(self) -> str:
        return self._config.s3gw_addr

    @property
    def access_key(self) -> str:
        return self._access_key

    @property
    def secret_key(self) -> str:
        return self._secret_key

    @property
    def addressing_style(self) -> Literal["auto", "virtual", "path"]:
        return self._config.s3_addressing_style.value

    @contextlib.asynccontextmanager
    async def conn(self, attempts: int = 1) -> AsyncGenerator[S3Client, None]:
        """
        Yields an `aiobotocore's S3Client` instance, that can be used to
        perform operations against an S3-compatible server. In case of failure,
        by default, the operation only performs one attempt.

        This context manager will catch most exceptions thrown by the
        `S3Client`'s operations, and convert them to `fastapi.HTTPException`.
        """
        session = AioSession()

        # aioboto3 behaves different from aiobotocore when it comes to the
        # registration of default handlers. Since we are not using the session
        # from aioboto3 here we have to do the registration ourselves. This is
        # necessary to get the `upload_fileobj` functionality.
        session.register(
            "creating-client-class.s3",
            boto3.utils.lazy_call(
                "aioboto3.s3.inject.inject_s3_transfer_methods"
            ),
        )

        async with session.create_client(  # noqa: E501 # pyright: ignore [reportUnknownMemberType]
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            verify=False,
            config=S3Config(
                retries={
                    "max_attempts": attempts,
                    "mode": "standard",
                },
                s3={
                    "addressing_style": self.addressing_style,
                },
            ),
        ) as client:
            try:
                yield cast(S3Client, client)
            except ClientError as e:
                (status_code, detail) = decode_client_error(e)
                raise HTTPException(status_code=status_code, detail=detail)
            except EndpointConnectionError as e:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=str(e),
                )
            except SSLError:
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail="SSL not supported",
                )
            except HTTPException as e:
                # probably an error raised by yielded client context; lets
                # propagate it.
                raise e
            except Exception as e:
                logger.error(f"Unknown error: {e}")
                logger.error(f"  exception: {type(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )


def decode_client_error(e: ClientError) -> Tuple[int, str]:
    """
    Returns a tuple of `(status_code, detail)` according to the
    `botocore's ClientError` exception that is passed as an argument.
    """
    status_code = pydash.get(
        e.response,
        "ResponseMetadata.HTTPStatusCode",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    detail = None
    code = pydash.get(e.response, "Error.Code")
    if code is not None:
        if code.isnumeric():
            status_code = int(code)
            detail = pydash.get(e.response, "Error.Message")
        else:
            detail = pydash.default_to(
                pydash.get(e.response, "Error.Message", code), code
            )
    return status_code, pydash.human_case(
        pydash.default_to(detail, "UnknownError")
    )


def s3gw_config(request: Request) -> Config:
    config: Config = request.app.state.config
    return config


async def s3gw_client(
    config: Annotated[Config, Depends(s3gw_config)],
    s3gw_credentials: Annotated[str, Header()],
) -> S3GWClient:
    """
    To be used for FastAPI's dependency injection, reads the request's HTTP
    headers for s3gw's user credentials, returning an `S3GWClient` class
    instance.
    """
    # credentials follow the format 'access_key:secret_key'
    m = re.fullmatch(r"^([\w+/=]+):([\w+/=]+)$", s3gw_credentials)
    if m is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing of malformed credentials",
        )

    assert len(m.groups()) == 2
    access, secret = m.group(1), m.group(2)
    assert len(access) > 0 and len(secret) > 0
    return S3GWClient(config, access, secret)


def s3gw_client_responses() -> Dict[int | str, Dict[str, Any]]:
    """
    Used to populate FastAPI's OpenAPI's method documentation, returns a
    dictionary containing the several error responses raised by `s3gw_client()`.
    """
    return {
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid credentials",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "Endpoint not found",
        },
        status.HTTP_501_NOT_IMPLEMENTED: {
            "description": "SSL not supported",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Unexpected error",
        },
    }
