#!/usr/bin/python3.4
#
#   Copyright 2017 - The Android Open Source Project
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

from acts.test_utils.wifi import wifi_test_utils as wutils
from acts.test_utils.wifi.aware import aware_const as aconsts
from acts.test_utils.wifi.aware import aware_test_utils as autils
from acts.test_utils.wifi.aware.AwareBaseTest import AwareBaseTest


class AttachTest(AwareBaseTest):
  def __init__(self, controllers):
    AwareBaseTest.__init__(self, controllers)

  def test_attach(self):
    """Functional test case / Attach test cases / attach

    Validates that attaching to the Wi-Fi Aware service works (receive
    the expected callback).
    """
    dut = self.android_devices[0]
    dut.droid.wifiAwareAttach(False)
    autils.wait_for_event(dut, aconsts.EVENT_CB_ON_ATTACHED)
    autils.fail_on_event(dut, aconsts.EVENT_CB_ON_IDENTITY_CHANGED)

  def test_attach_with_identity(self):
    """Functional test case / Attach test cases / attach with identity callback

    Validates that attaching to the Wi-Fi Aware service works (receive
    the expected callbacks).
    """
    dut = self.android_devices[0]
    dut.droid.wifiAwareAttach(True)
    autils.wait_for_event(dut, aconsts.EVENT_CB_ON_ATTACHED)
    autils.wait_for_event(dut, aconsts.EVENT_CB_ON_IDENTITY_CHANGED)

  def test_attach_multiple_sessions(self):
    """Functional test case / Attach test cases / multiple attach sessions

    Validates that when creating multiple attach sessions each can be
    configured independently as to whether or not to receive an identity
    callback.
    """
    dut = self.android_devices[0]

    # Create 3 attach sessions: 2 without identity callback, 1 with
    id1 = dut.droid.wifiAwareAttach(False, None, True)
    id2 = dut.droid.wifiAwareAttach(True, None, True)
    id3 = dut.droid.wifiAwareAttach(False, None, True)
    dut.log.info('id1=%d, id2=%d, id3=%d', id1, id2, id3)

    # Attach session 1: wait for attach, should not get identity
    autils.wait_for_event(dut,
                          autils.decorate_event(aconsts.EVENT_CB_ON_ATTACHED,
                                                id1))
    autils.fail_on_event(dut,
                         autils.decorate_event(
                             aconsts.EVENT_CB_ON_IDENTITY_CHANGED, id1))

    # Attach session 2: wait for attach and for identity callback
    autils.wait_for_event(dut,
                          autils.decorate_event(aconsts.EVENT_CB_ON_ATTACHED,
                                                id2))
    autils.wait_for_event(dut,
                          autils.decorate_event(
                              aconsts.EVENT_CB_ON_IDENTITY_CHANGED, id2))

    # Attach session 3: wait for attach, should not get identity
    autils.wait_for_event(dut,
                          autils.decorate_event(aconsts.EVENT_CB_ON_ATTACHED,
                                                id3))
    autils.fail_on_event(dut,
                         autils.decorate_event(
                             aconsts.EVENT_CB_ON_IDENTITY_CHANGED, id3))

  def test_attach_with_no_wifi(self):
    """Function test case / Attach test cases / attempt to attach with wifi off

    Validates that if trying to attach with Wi-Fi disabled will receive the
    expected failure callback. As a side-effect also validates that the broadcast
    for Aware unavailable is received.
    """
    dut = self.android_devices[0]
    wutils.wifi_toggle_state(dut, False)
    autils.wait_for_event(dut, aconsts.BROADCAST_WIFI_AWARE_NOT_AVAILABLE)
    dut.droid.wifiAwareAttach()
    autils.wait_for_event(dut, aconsts.EVENT_CB_ON_ATTACH_FAILED)