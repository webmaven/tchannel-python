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
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import subprocess
import textwrap
from mock import MagicMock, patch, ANY

import json
import os
import psutil
import pytest
from tornado import gen

from tchannel import TChannel, Request, Response, schemes, errors
from tchannel.errors import AlreadyListeningError, TimeoutError
from tchannel.event import EventHook
from tchannel.response import TransportHeaders

# TODO - need integration tests for timeout and retries, use testing.vcr


@pytest.mark.call
def test_should_have_default_schemes():

    tchannel = TChannel(name='test')

    for f in schemes.DEFAULT_SCHEMES:
        scheme = getattr(tchannel, f.NAME)
        assert scheme, "default scheme not found"
        assert isinstance(scheme, f)


@pytest.mark.gen_test
@pytest.mark.call
def test_call_should_get_response():

    # Given this test server:

    server = TChannel(name='server')

    @server.register(scheme=schemes.RAW)
    def endpoint(request):

        assert isinstance(request, Request)
        assert request.headers == 'req headers'
        assert request.body == 'req body'

        return Response('resp body', 'resp headers')

    server.listen()

    # Make a call:

    tchannel = TChannel(name='client')

    resp = yield tchannel.call(
        scheme=schemes.RAW,
        service='server',
        arg1='endpoint',
        arg2='req headers',
        arg3='req body',
        hostport=server.hostport,
    )

    # verify response
    assert isinstance(resp, Response)
    assert resp.headers == 'resp headers'
    assert resp.body == 'resp body'

    # verify response transport headers
    assert isinstance(resp.transport, TransportHeaders)
    assert resp.transport.scheme == schemes.RAW
    assert resp.transport.failure_domain is None


@pytest.mark.gen_test
@pytest.mark.call
def test_timeout_should_raise_timeout_error():

    # Given this test server:

    server = TChannel(name='server')

    @server.register(scheme=schemes.RAW)
    @gen.coroutine
    def endpoint(request):
        yield gen.sleep(0.05)
        raise gen.Return('hello')

    server.listen()

    # Make a call:

    tchannel = TChannel(name='client')

    # timeout is less than server, should timeout
    with pytest.raises(TimeoutError):
        yield tchannel.call(
            scheme=schemes.RAW,
            service='server',
            arg1='endpoint',
            hostport=server.hostport,
            timeout=0.02,
        )

    # timeout is more than server, should not timeout
    yield tchannel.raw(
        service='server',
        endpoint='endpoint',
        hostport=server.hostport,
        timeout=0.1,
    )


def test_uninitialized_tchannel_is_fork_safe():
    """TChannel('foo') should not schedule any work on the io loop."""

    process = psutil.Popen(
        [
            'python',
            '-c',
            textwrap.dedent(
                """
                import os
                from tchannel import TChannel
                t = TChannel("app")
                os.fork()
                t.listen()
                """
            ),
        ],
        stderr=subprocess.PIPE,
    )

    try:
        stderr = process.stderr.read()
        ret = process.wait()
        assert ret == 0 and not stderr, stderr
    finally:
        if process.is_running():
            process.kill()


@pytest.mark.gen_test
@pytest.mark.call
def test_headers_and_body_should_be_optional():

    # Given this test server:

    server = TChannel(name='server')

    @server.register(scheme=schemes.RAW)
    def endpoint(request):
        # assert request.headers is None  # TODO uncomment
        # assert request.body is None  # TODO uncomment
        pass

    server.listen()

    # Make a call:

    tchannel = TChannel(name='client')

    resp = yield tchannel.call(
        scheme=schemes.RAW,
        service='server',
        arg1='endpoint',
        hostport=server.hostport,
    )

    # verify response
    assert isinstance(resp, Response)
    assert resp.headers == ''  # TODO should be None to match server
    assert resp.body == ''  # TODO should be None to match server


@pytest.mark.gen_test
@pytest.mark.call
def test_endpoint_can_return_just_body():

    # Given this test server:

    server = TChannel(name='server')

    @server.register(scheme=schemes.RAW)
    def endpoint(request):
        return 'resp body'

    server.listen()

    # Make a call:

    tchannel = TChannel(name='client')

    resp = yield tchannel.call(
        scheme=schemes.RAW,
        service='server',
        arg1='endpoint',
        hostport=server.hostport,
    )

    # verify response
    assert isinstance(resp, Response)
    assert resp.headers == ''  # TODO should be is None to match server
    assert resp.body == 'resp body'


# TODO - verify register programmatic use cases

@pytest.mark.gen_test
@pytest.mark.call
def test_endpoint_can_be_called_as_a_pure_func():

    # Given this test server:

    server = TChannel(name='server')

    @server.register(scheme=schemes.RAW)
    def endpoint(request):

        assert isinstance(request, Request)
        assert request.body == 'req body'
        assert request.headers == 'req headers'

        return Response('resp body', headers='resp headers')

    server.listen()

    # Able to call over TChannel

    tchannel = TChannel(name='client')

    resp = yield tchannel.call(
        scheme=schemes.RAW,
        service='server',
        arg1='endpoint',
        arg2='req headers',
        arg3='req body',
        hostport=server.hostport,
    )

    assert isinstance(resp, Response)
    assert resp.headers == 'resp headers'
    assert resp.body == 'resp body'

    # Able to call as function

    resp = endpoint(Request('req body', headers='req headers'))

    assert isinstance(resp, Response)
    assert resp.headers == 'resp headers'
    assert resp.body == 'resp body'


@pytest.mark.gen_test
@pytest.mark.call
def test_endpoint_not_found_with_raw_request():
    server = TChannel(name='server')
    server.listen()

    tchannel = TChannel(name='client')

    with pytest.raises(errors.BadRequestError) as e:
        yield tchannel.raw(
            service='server',
            hostport=server.hostport,
            endpoint='foo',
        )

    assert "Endpoint 'foo' is not defined" in e.value


@pytest.mark.gen_test
@pytest.mark.call
def test_endpoint_not_found_with_json_request():
    server = TChannel(name='server')
    server.listen()

    tchannel = TChannel(name='client')

    with pytest.raises(errors.BadRequestError) as e:
        yield tchannel.json(
            service='server',
            hostport=server.hostport,
            endpoint='foo',
        )

    assert "Endpoint 'foo' is not defined" in e.value


def test_event_hook_register():
    server = TChannel(name='server')
    mock_hook = MagicMock(spec=EventHook)
    with (
        patch(
            'tchannel.event.EventRegistrar.register',
            autospec=True,
        )
    ) as mock_register:
        server.hooks.register(mock_hook)
        mock_register.called


@pytest.mark.gen_test
def test_advertise_should_take_a_router_file():

    host_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'data/hosts.json',
    )

    tchannel = TChannel(name='client')
    with open(host_path, 'r') as json_data:
        routers = json.load(json_data)

    with (
        patch(
            'tchannel.tornado.TChannel.advertise',
            autospec=True,
        )
    ) as mock_advertise:
        f = gen.Future()
        mock_advertise.return_value = f
        f.set_result(Response())
        tchannel.advertise(router_file=host_path)

        mock_advertise.assert_called_once_with(ANY, routers=routers,
                                               name=ANY, timeout=ANY)


@pytest.mark.gen_test
def test_advertise_should_raise_on_invalid_router_file():

    tchannel = TChannel(name='client')
    with pytest.raises(IOError):
        yield tchannel.advertise(router_file='?~~lala')

    with pytest.raises(ValueError):
        yield tchannel.advertise(routers='lala', router_file='?~~lala')


def test_listen_different_ports():
    server = TChannel(name='test_server')
    server.listen()
    port = int(server.hostport.rsplit(":")[1])
    with pytest.raises(AlreadyListeningError):
        server.listen(port + 1)


def test_listen_duplicate_ports():
    server = TChannel(name='test_server')
    server.listen()
    server.listen()
    port = int(server.hostport.rsplit(":")[1])
    server.listen(port)
    server.listen()
