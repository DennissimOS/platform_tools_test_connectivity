#!/usr/bin/env python3.4
#
#   Copyright 2016 - The Android Open Source Project
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

import os

import acts.base_test
from acts import utils
from acts.controllers import monsoon
from acts.test_utils.wifi import wifi_test_utils as wutils
from acts.test_utils.tel import tel_test_utils as tel_utils

pmc_base_cmd = ("am broadcast -a com.android.pmc.action.AUTOPOWER --es"
                " PowerAction ")
start_pmc_cmd = ("am start -n com.android.pmc/com.android.pmc."
    "PMCMainActivity")
pmc_start_connect_scan_cmd = "%sStartConnectivityScan" % pmc_base_cmd
pmc_stop_connect_scan_cmd = "%sStopConnectivityScan" % pmc_base_cmd
pmc_start_gscan_no_dfs_cmd = "%sStartGScanBand" % pmc_base_cmd
pmc_start_gscan_specific_channels_cmd = "%sStartGScanChannel" % pmc_base_cmd
pmc_stop_gscan_cmd = "%sStopGScan" % pmc_base_cmd
pmc_start_1MB_download_cmd = "%sDownload1MB" % pmc_base_cmd
pmc_stop_1MB_download_cmd = "%sStopDownload" % pmc_base_cmd

class WifiPowerTest(acts.base_test.BaseTestClass):

    def __init__(self, controllers):
        super(WifiPowerTest, self).__init__(controllers)
        self.tests = (
            "test_power_wifi_off",
            "test_power_wifi_on_idle",
            "test_power_wifi_on_idle",
            "test_power_disconnected_connectivity_scan",
            "test_power_connected_to_2g_idle",
            "test_power_connected_2g_download_1MB",
            "test_power_connected_to_5g_idle",
            "test_power_connected_to_5g_download_1MB",
            "test_power_gscan_three_2g_channels",
            "test_power_gscan_all_channels_no_dfs"
        )

    def setup_class(self):
        self.hz = 10
        self.offset = 5 * 60
        self.duration = 30 * 60 + self.offset
        self.mon_data_path = os.path.join(self.log_path, "Monsoon")

        self.mon = self.monsoons[0]
        self.mon.set_voltage(4.2)
        self.mon.set_max_current(7.8)
        self.dut = self.android_devices[0]
        self.mon.attach_device(self.dut)
        self.assert_true(self.mon.usb("auto"),
                         "Failed to turn USB mode to auto on monsoon.")
        required_userparam_names = (
            # These two params should follow the format of
            # {"SSID": <SSID>, "password": <Password>}
            "network_2g",
            "network_5g"
        )
        self.unpack_userparams(required_userparam_names)
        wutils.wifi_test_device_init(self.dut)
        # Start pmc app.
        self.dut.adb.shell(start_pmc_cmd)

    def teardown_class(self):
        wutils.reset_wifi(self.dut)

    def setup_test(self):
        wutils.reset_wifi(self.dut)
        self.dut.ed.clear_all_events()

    def measure_and_process_result(self):
        tag = self.current_test_name
        result = self.mon.measure_power(self.hz,
                                        self.duration,
                                        tag=tag,
                                        offset=self.offset)
        self.assert_true(result, "Got empty measurement data set in %s." % tag)
        self.log.info(repr(result))
        data_path = os.path.join(self.mon_data_path, "%s.txt" % tag)
        monsoon.MonsoonData.save_to_text_file([result], data_path)
        actual_current = "%.2fmA" % result.average_current
        self.explicit_pass("Measurement finished for %s." % tag,
                           extras={"Average Current": actual_current})

    def test_power_wifi_off(self):
        self.assert_true(wutils.wifi_toggle_state(self.dut, False),
                         "Failed to toggle wifi off.")
        self.measure_and_process_result()

    def test_power_wifi_on_idle(self):
        self.assert_true(wutils.wifi_toggle_state(self.dut, True),
                         "Failed to toggle wifi on.")
        self.measure_and_process_result()

    def test_power_disconnected_connectivity_scan(self):
        try:
            self.dut.adb.shell(pmc_start_connect_scan_cmd)
            self.log.info("Started connectivity scan.")
            self.measure_and_process_result()
        finally:
            self.dut.adb.shell(pmc_stop_connect_scan_cmd)
            self.log.info("Stoped connectivity scan.")

    def test_power_connected_to_2g_idle(self):
        wutils.wifi_connect(self.dut, self.network_2g)
        self.measure_and_process_result()

    def test_power_connected_2g_download_1MB(self):
        try:
            self.dut.adb.shell(pmc_start_1MB_download_cmd)
            self.log.info("Start downloading 1MB file consecutively.")
            self.measure_and_process_result()
        finally:
            self.dut.adb.shell(pmc_stop_1MB_download_cmd)
            self.log.info("Stopped downloading 1MB file.")

    def test_power_connected_to_5g_idle(self):
        wutils.reset_wifi(self.dut)
        self.dut.ed.clear_all_events()
        wutils.wifi_connect(self.dut, self.network_5g)
        self.measure_and_process_result()

    def test_power_connected_to_5g_download_1MB(self):
        try:
            self.dut.adb.shell(pmc_start_1MB_download_cmd)
            self.log.info("Started downloading 1MB file consecutively.")
            self.measure_and_process_result()
        finally:
            self.dut.adb.shell(pmc_stop_1MB_download_cmd)
            self.log.info("Stopped downloading 1MB file.")

    def test_power_gscan_three_2g_channels(self):
        try:
            self.dut.adb.shell(pmc_start_gscan_specific_channels_cmd)
            self.log.info("Started gscan for 2G channels 1, 6, and 11.")
            self.measure_and_process_result()
        finally:
            self.dut.adb.shell(pmc_stop_gscan_cmd)
            self.log.info("Stopped gscan.")

    def test_power_gscan_all_channels_no_dfs(self):
        try:
            self.dut.adb.shell(pmc_start_gscan_no_dfs_cmd)
            self.log.info("Started gscan for all non-DFS channels.")
            self.measure_and_process_result()
        finally:
            self.dut.adb.shell(pmc_stop_gscan_cmd)
            self.log.info("Stopped gscan.")
