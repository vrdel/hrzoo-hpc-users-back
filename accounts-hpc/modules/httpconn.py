import ssl
import asyncio
import aiohttp
import random

from aiohttp import client_exceptions, http_exceptions
from accounts_hpc.exceptions import SyncHttpError


def module_class_name(obj):
    name = repr(obj.__class__.__name__)

    return name.replace("'", '')


def build_ssl_settings(confopts):
    try:
        sslcontext = ssl.create_default_context(cafile=confopts['authentication']['cafile'])

        return sslcontext

    except KeyError:
        return None


def build_connection_retry_settings(confopts):
    retry = int(confopts['connection']['retry'])
    timeout = int(confopts['connection']['timeout'])
    return (retry, timeout)


class SessionWithRetry(object):
    def __init__(self, logger, confopts, auth=None, handle_session_close=False):
        self.ssl_context = build_ssl_settings(confopts)
        n_try, client_timeout = build_connection_retry_settings(confopts)
        client_timeout = aiohttp.ClientTimeout(total=client_timeout,
                                               connect=client_timeout, sock_connect=client_timeout,
                                               sock_read=client_timeout)
        self.session = aiohttp.ClientSession(timeout=client_timeout)
        self.confopts = confopts
        if auth:
            self.auth = aiohttp.BasicAuth(login=auth[0], password=auth[1])
        else:
            self.auth = None

        self.n_try = n_try
        self.logger = logger
        self.token = confopts['hzsiapi']['token']
        self.handle_session_close = handle_session_close
        self.erroneous_statuses = [404, 403]

    async def _http_method(self, method, url, data=None, headers=None):
        method_obj = getattr(self.session, method)
        raised_exc = None
        n = 1
        # if self.token:
            # headers = headers or {}
            # headers.update({
                # 'Authorization': f'Api-Key {self.token}',
                # 'Accept': 'application/json'
            # })
        try:
            sleepsecs = float(self.confopts['connection']['sleepretry'])

            while n <= self.n_try:
                if n > 1:
                    self.logger.info(f"{module_class_name(self)} : HTTP Connection try - {n} after sleep {sleepsecs} seconds")
                try:
                    async with method_obj(url, data=data, headers=headers,
                                          ssl=self.ssl_context, auth=self.auth) as response:

                        if response.status in self.erroneous_statuses:
                            self.logger.error('{}.http_{}({}) - Erroneous HTTP status: {} {}'.
                                              format(module_class_name(self),
                                                     method, url,
                                                     response.status,
                                                     response.reason))
                            break
                        content = await response.text()
                        if content:
                            return content

                        self.logger.warn("{} : HTTP Empty response".format(module_class_name(self)))

                # do not retry on SSL errors
                # raise exc that will be handled in outer try/except clause
                except ssl.SSLError as exc:
                    raise exc

                # retry on client errors
                except (client_exceptions.ClientError,
                        client_exceptions.ServerTimeoutError,
                        asyncio.TimeoutError) as exc:
                    self.logger.error('{}.http_{}({}) - {}'.format(module_class_name(self), method, url, repr(exc)))
                    raised_exc = exc

                # do not retry on HTTP protocol errors
                # raise exc that will be handled in outer try/except clause
                except (http_exceptions.HttpProcessingError) as exc:
                    self.logger.error('{}.http_{}({}) - {}'.format(module_class_name(self), method, url, repr(exc)))
                    raise exc

                await asyncio.sleep(sleepsecs)
                n += 1

            else:
                self.logger.info("{} : HTTP Connection retry exhausted".format(module_class_name(self)))
                raise raised_exc

        except Exception as exc:
            self.logger.error('{}.http_{}({}) - {}'.format(module_class_name(self), method, url, repr(exc)))
            raise exc

        finally:
            if not self.handle_session_close:
                await self.session.close()

    async def http_get(self, url, headers=None):
        try:
            content = await self._http_method('get', url, headers=headers)
            return content

        except Exception as exc:
            raise SyncHttpError(repr(exc)) from exc

    async def close(self):
        return await self.session.close()
