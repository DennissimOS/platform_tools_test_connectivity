#!/usr/bin/env python3.4

# Copyright 2016 - The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
import os
import sys
import unittest

from acts.libs.proc import job


PY_ERR_CODE = "import sys\n" + \
              "sys.stderr.write('TEST')\n"


class BackgroundJobTestCases(unittest.TestCase):
    def test_background_job(self):
        """Test running a BackgroundJob

        Runs a simple BackgroundJob to and checks its standard output to see
        if it ran.
        """
        my_job = job.BackgroundJob('echo TEST')

        self.assertTrue(my_job.result.stdout.startswith('TEST'))

    def test_background_job_in(self):
        """Test if a background job can send through standard input.

        Sends a line through standard input to see if the BackgroundJob can
        pick it up.
        """
        my_job = job.BackgroundJob('grep "TEST"', allow_send=True)

        my_job.sendline('TEST')

        self.assertTrue(my_job.result.stdout.startswith('TEST'))

    def test_background_job_instream(self):
        """Test if a background job can pipe its stdin.

        Sends standard input to the BackgroundJob through a different
        stream.
        """
        stream = io.BytesIO()

        my_job = job.BackgroundJob('grep "TEST"', stdin=stream)

        # In a real situation a pipe would probably be used, however writing
        # and then seeking is simpiler for the sake of testing.
        stream.write('TEST'.encode())
        stream.seek(0)

        self.assertTrue(my_job.result.stdout.startswith('TEST'))

    def test_background_job_err(self):
        """Test reading standard err.

        Launches a BackgroundJob that writes to standard error to see if
        it gets captured.
        """
        my_job = job.BackgroundJob('python', stdin=PY_ERR_CODE)

        self.assertTrue(my_job.result.stderr.startswith('TEST'))

    def test_background_job_pipe(self):
        """Test piping on a BackgroundJob.

        Tests that the standard output of a job can be piped to another stream.
        """
        mem_buffer = io.StringIO()
        my_job = job.BackgroundJob('echo TEST', stdout_tee=mem_buffer)

        my_job.wait()

        self.assertTrue(mem_buffer.getvalue().startswith('TEST'))

    def test_background_job_pipe_err(self):
        """Test error piping on a BackgroundJob.

        Tests that the standard output of a job can be piped to another stream.
        """
        mem_buffer = io.StringIO()
        my_job = job.BackgroundJob("python",
                                   stdin=PY_ERR_CODE,
                                   stderr_tee=mem_buffer)

        my_job.wait()

        self.assertTrue(mem_buffer.getvalue().startswith('TEST'))

    def test_background_job_timeout(self):
        with self.assertRaises(job.TimeoutError):
            my_job = job.BackgroundJob('sleep 5')
            my_job.wait(timeout=0.1)

    def test_background_job_env(self):
        my_job = job.BackgroundJob('printenv', env={'MYTESTVAR': '20'})

        self.assertNotEqual(my_job.result.stdout.find('MYTESTVAR=20'), -1)


if __name__ == '__main__':
    unittest.main()
