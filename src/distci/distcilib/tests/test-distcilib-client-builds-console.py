"""
Tests for clientlib/builds/console

Copyright (c) 2013 Heikki Nousiainen, F-Secure
See LICENSE for details
"""

import tempfile
import os
import shutil
import threading
import urllib2
import wsgiref.simple_server

from distci.frontend import frontend

from distci import distcilib

class BackgroundHttpServer:
    def __init__(self, server):
        self.server = server

    def serve(self):
        self.server.serve_forever()

class SilentWSGIRequestHandler(wsgiref.simple_server.WSGIRequestHandler):
    def log_message(self, *args):
        pass

class TestDistcilibClientTasks:
    app = None
    config_file = None
    data_directory = None
    state = {}

    @classmethod
    def setUpClass(cls):
        cls.data_directory = tempfile.mkdtemp()
        os.mkdir(os.path.join(cls.data_directory, 'jobs'))

        frontend_config = { "data_directory": cls.data_directory }

        cls.frontend_app = frontend.Frontend(frontend_config)

        cls.server = wsgiref.simple_server.make_server('localhost', 0, cls.frontend_app.handle_request, handler_class=SilentWSGIRequestHandler)
        cls.server_port = cls.server.socket.getsockname()[1]

        cls.slave = BackgroundHttpServer(cls.server)
        cls.slave_thread = threading.Thread(target=cls.slave.serve)
        cls.slave_thread.start()

        client_config = { 'frontends': [ 'http://localhost:%d/' % cls.server_port ],
                          'task_frontends' : [ 'http://localhost:%d/' % cls.server_port ] }
        cls.client = distcilib.DistCIClient(client_config)

        cls.state = { }

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.slave_thread.join()
        shutil.rmtree(cls.data_directory)

    def test_00_setup(self):
        job_config = { 'job_id': 'testjob' }
        job = self.client.jobs.create(job_config)
        assert job is not None, "Empty result for job creation"
        self.state['job_id'] = job['job_id']

        build = self.client.builds.trigger(self.state['job_id'])
        assert build is not None, "Empty result for trigger build"
        assert build.get('job_id') == self.state['job_id'], "Job ID mismatch"
        assert build.has_key('build_number'), "Build number went missing"
        self.state['build_number'] = build['build_number']

    def test_01_get_console(self):
        reply = self.client.builds.console.get(self.state['job_id'], self.state['build_number'])
        assert reply is not None, "Failed to get console log"
        assert reply == '', "Non-empty console"

    def test_02_append_console(self):
        self.state['console_contents'] = 'console content\n'
        reply = self.client.builds.console.append(self.state['job_id'], self.state['build_number'], self.state['console_contents'])
        assert reply == True, "Failed to append console log"

        reply = self.client.builds.console.get(self.state['job_id'], self.state['build_number'])
        assert reply is not None, "Failed to get console log"
        assert reply == self.state['console_contents'], "Wrong data"

    def test_03_update_console(self):
        new_data = 'additional content\n'
        self.state['console_contents'] = '%s%s' % (self.state['console_contents'], new_data)
        reply = self.client.builds.console.append(self.state['job_id'], self.state['build_number'], new_data)
        assert reply == True, "Failed to append console log"

        reply = self.client.builds.console.get(self.state['job_id'], self.state['build_number'])
        assert reply is not None, "Failed to get console log"
        assert reply == self.state['console_contents'], "Wrong data"

