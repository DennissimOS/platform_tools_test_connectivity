#!/usr/bin/env python3.4
#
#   Copyright 2018 - The Android Open Source Project
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

import time
import acts.signals as signals
import acts.test_utils.wifi.wifi_test_utils as wutils
from acts import asserts
from acts import utils
from acts.test_decorators import test_tracker_info
from acts.test_utils.wifi.WifiBaseTest import WifiBaseTest
from acts.test_utils.tel.tel_test_utils import disable_qxdm_logger

WifiEnums = wutils.WifiEnums

class WifiCrashStressTest(WifiBaseTest):
    """Crash Tests for wifi stack.

    Test Bed Requirement:
    * Two Android device
    * One Wi-Fi network visible to the device.
    """

    def __init__(self, controllers):
        WifiBaseTest.__init__(self, controllers)

    def setup_class(self):
        self.dut = self.android_devices[0]
        self.dut_client = self.android_devices[1]
        wutils.wifi_test_device_init(self.dut)
        wutils.wifi_test_device_init(self.dut_client)
        if not self.dut.is_apk_installed("com.google.mdstest"):
            raise signals.TestSkipClass("mdstest is not installed")
        req_params = ["dbs_supported_models", "stress_count"]
        opt_param = ["reference_networks"]
        self.unpack_userparams(
            req_param_names=req_params, opt_param_names=opt_param)

        if "AccessPoint" in self.user_params:
            self.legacy_configure_ap_and_start()

        asserts.assert_true(
            len(self.reference_networks) > 0,
            "Need at least one reference network with psk.")
        self.network = self.reference_networks[0]["2g"]

    def setup_test(self):
        self.dut.droid.wakeLockAcquireBright()
        self.dut.droid.wakeUpNow()
        wutils.wifi_toggle_state(self.dut, True)
        self.dut_client.droid.wakeLockAcquireBright()
        self.dut_client.droid.wakeUpNow()
        wutils.wifi_toggle_state(self.dut_client, True)

    def teardown_test(self):
        if self.dut.droid.wifiIsApEnabled():
            wutils.stop_wifi_tethering(self.dut)
        self.dut.droid.wakeLockRelease()
        self.dut.droid.goToSleepNow()
        wutils.reset_wifi(self.dut)
        self.dut_client.droid.wakeLockRelease()
        self.dut_client.droid.goToSleepNow()
        wutils.reset_wifi(self.dut_client)

    def on_fail(self, test_name, begin_time):
        self.dut.take_bug_report(test_name, begin_time)
        self.dut.cat_adb_log(test_name, begin_time)
        self.dut_client.take_bug_report(test_name, begin_time)
        self.dut_client.cat_adb_log(test_name, begin_time)

    def teardown_class(self):
        if "AccessPoint" in self.user_params:
            del self.user_params["reference_networks"]

    """Helper Functions"""
    def trigger_wifi_firmware_crash(self, ad, timeout=30):
        pre_timestamp = ad.adb.getprop("vendor.debug.ssrdump.timestamp")
        ad.adb.shell(
            "setprop persist.vendor.sys.modem.diag.mdlog false", ignore_status=True)
        # Legacy pixels use persist.sys.modem.diag.mdlog.
        ad.adb.shell(
            "setprop persist.sys.modem.diag.mdlog false", ignore_status=True)
        disable_qxdm_logger(ad)
        cmd = ('am instrument -w -e request "4b 25 03 b0 00" '
               '"com.google.mdstest/com.google.mdstest.instrument.'
               'ModemCommandInstrumentation"')
        ad.log.info("Crash wifi firmware by %s", cmd)
        ad.adb.shell(cmd, ignore_status=True)
        time.sleep(timeout)  # sleep time for firmware restart
        subsystem = ad.adb.getprop("vendor.debug.ssrdump.subsys")
        timestamp = ad.adb.getprop("vendor.debug.ssrdump.timestamp")
        asserts.assert_true(timestamp != pre_timestamp,
            "SSR didn't happened %s %s" % (subsystem, timestamp))

    """Tests"""
    @test_tracker_info(uuid="")
    def test_firmware_crash_wifi_reconnect_stress(self):
        """Firmware crash stress test for station mode

        1. Turn on Wi-Fi and connect to access point
        2. Trigger firmware crash
        3. Check ssr happened
        4. Check dut can connect to access point
        5. Repeat step 2~4
        """
        wutils.wifi_toggle_state(self.dut, True)
        wutils.connect_to_wifi_network(self.dut, self.network)
        for count in range(self.stress_count):
            self.log.info("%s: %d/%d" %
                (self.current_test_name, count + 1, self.stress_count))
            wutils.reset_wifi(self.dut)
            self.trigger_wifi_firmware_crash(self.dut)
            wutils.connect_to_wifi_network(self.dut, self.network)

    @test_tracker_info(uuid="")
    def test_firmware_crash_softap_reconnect_stress(self):
        """Firmware crash stress test for softap mode

        1. Turn off dut's Wi-Fi
        2. Turn on dut's hotspot and connected by dut client
        3. Trigger firmware crash
        4. Check ssr happened
        5. Check the connectivity of hotspot's client
        6. Repeat step 3~5
        """
        wutils.wifi_toggle_state(self.dut, False)
        # Setup Soft AP
        sap_config = wutils.create_softap_config()
        wutils.start_wifi_tethering(
            self.dut, sap_config[wutils.WifiEnums.SSID_KEY],
            sap_config[wutils.WifiEnums.PWD_KEY], wutils.WifiEnums.WIFI_CONFIG_APBAND_2G)
        config = {
            "SSID": sap_config[wutils.WifiEnums.SSID_KEY],
            "password": sap_config[wutils.WifiEnums.PWD_KEY]
        }
        # DUT client connects to softap
        wutils.wifi_toggle_state(self.dut_client, True)
        wutils.connect_to_wifi_network(self.dut_client, config, check_connectivity=False)
        # Ping the DUT
        dut_addr = self.dut.droid.connectivityGetIPv4Addresses("wlan0")[0]
        asserts.assert_true(
            utils.adb_shell_ping(self.dut_client, count=10, dest_ip=dut_addr, timeout=20),
            "%s ping %s failed" % (self.dut_client.serial, dut_addr))
        wutils.reset_wifi(self.dut_client)
        for count in range(self.stress_count):
            self.log.info("%s: %d/%d" %
                (self.current_test_name, count + 1, self.stress_count))
            # Trigger firmware crash
            self.trigger_wifi_firmware_crash(self.dut)
            # Connect DUT to Network
            wutils.wifi_toggle_state(self.dut_client, True)
            wutils.connect_to_wifi_network(self.dut_client, config, check_connectivity=False)
            # Ping the DUT
            server_addr = self.dut.droid.connectivityGetIPv4Addresses("wlan0")[0]
            asserts.assert_true(
                utils.adb_shell_ping(self.dut_client, count=10, dest_ip=dut_addr, timeout=20),
                "%s ping %s failed" % (self.dut_client.serial, dut_addr))
        wutils.stop_wifi_tethering(self.dut)

    @test_tracker_info(uuid="")
    def test_firmware_crash_concurrent_reconnect_stress(self):
        """Firmware crash stress test for concurrent mode

        1. Turn on dut's Wi-Fi and connect to access point
        2. Turn on dut's hotspot and connected by dut client
        3. Trigger firmware crash
        4. Check ssr happened
        5. Check dut can connect to access point
        6. Check the connectivity of hotspot's client
        7. Repeat step 3~6
        """
        if self.dut.model not in self.dbs_supported_models:
            raise signals.TestSkip("%s does not support dual interfaces" % self.dut.model)

        # Connect DUT to Network
        wutils.wifi_toggle_state(self.dut, True)
        wutils.connect_to_wifi_network(self.dut, self.network)
        # Setup Soft AP
        sap_config = wutils.create_softap_config()
        wutils.start_wifi_tethering(
            self.dut, sap_config[wutils.WifiEnums.SSID_KEY],
            sap_config[wutils.WifiEnums.PWD_KEY], wutils.WifiEnums.WIFI_CONFIG_APBAND_2G)
        config = {
            "SSID": sap_config[wutils.WifiEnums.SSID_KEY],
            "password": sap_config[wutils.WifiEnums.PWD_KEY]
        }
        # Client connects to Softap
        wutils.wifi_toggle_state(self.dut_client, True)
        wutils.connect_to_wifi_network(self.dut_client, config)
        wutils.reset_wifi(self.dut_client)
        wutils.reset_wifi(self.dut)
        for count in range(self.stress_count):
            self.log.info("%s: %d/%d" %
                (self.current_test_name, count + 1, self.stress_count))
            # Trigger firmware crash
            self.trigger_wifi_firmware_crash(self.dut)
            wutils.connect_to_wifi_network(self.dut, self.network)
            wutils.connect_to_wifi_network(self.dut_client, config)
        wutils.stop_wifi_tethering(self.dut)
