# Copyright (c) 2015 Uber Technologies, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from __future__ import absolute_import

from thrift import Thrift

from tornado import gen
from tornado import ioloop
try:
    from tornado.queues import Queue  # Included in Tornado 4.2
except ImportError:
    from toro import Queue

from tchannel.messages.common import Types
from .base import TChannelTransportBase


class TChannelTornadoTransportBase(TChannelTransportBase):
    """A Thrift Transport to send requests over an open TChannel connection.

    Works with Thrift clients generated with the ``tornado`` option enabled.

    .. code-block::

        transport = TChannelTornadoTransport(
            tchannel, host_port, 'foo_service'
        )
        transport.init_call('FooService::doBar')
        transport.write('request body')
        transport.flush()

        response_body = yield transport.readFrame()

    VERY IMPORTANT IMPLEMENTATION DETAIL: For Tornado responses, Thrift calls
    ``readFrame`` which produces the serialized payload. It then constructs a
    ``TMemoryBuffer`` and gets all the response details out of that. So we
    have no way of communicating response details from the
    ``CallResponseMessage`` to the ``TChannelProtocol``. To work around that,
    there's a janky hack in place: When we receive a response, we prepend the
    missing information (endpoint name, message type, and seqid) to the
    payload. ``TChannelProtocolFramed`` knows how to read this.
    ``TChannelProtocolFactory`` automatically uses a
    ``TChannelProtocolFramed`` if the transport being used is not a
    ``TChannelTransportBase``.
    """

    def __init__(self, hostport, service_name, io_loop=None):
        super(TChannelTornadoTransportBase, self).__init__(
            hostport, service_name
        )

        self._response_queue = Queue()
        self.io_loop = io_loop or ioloop.IOLoop.current()

    def readFrame(self):
        return self._response_queue.get()

    def read(self, n):
        raise NotImplementedError(
            "read() must not be called directly. Use readFrame()."
        )

    def recv_call(self):
        raise NotImplementedError(
            "recv_call() not supported for Tornado. Use readFrame()."
        )

    @gen.coroutine
    def flush(self):
        raise NotImplementedError("Must be implemented.")

    @classmethod
    def _to_tappexception(cls, response):
        # TODO: map error codes to TApplicationException error types
        # TODO: move this into parent class and use in TChannelTransport
        assert response.message_type == Types.ERROR
        return Thrift.TApplicationException(message=response.message)