#!/usr/bin/python3.4
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

import json
import pprint
import re
import queue

from acts import asserts
from acts import base_test
from acts.test_utils.wifi import wifi_test_utils as wutils

WIFI_NAN_ENABLED = "WifiNanEnabled"
WIFI_NAN_DISABLED = "WifiNanDisabled"
ON_CONNECT_SUCCESS = "WifiNanOnConnectSuccess"
ON_NAN_DOWN = "WifiNanOnNanDown"
ON_MATCH = "WifiNanSessionOnMatch"
ON_MESSAGE_RX = "WifiNanSessionOnMessageReceived"
ON_MESSAGE_TX_FAIL = "WifiNanSessionOnMessageSendFail"
ON_MESSAGE_TX_OK = "WifiNanSessionOnMessageSendSuccess"
ON_RANGING_SUCCESS = "WifiNanRangingListenerOnSuccess"
ON_RANGING_FAILURE = "WifiNanRangingListenerOnFailure"
ON_RANGING_ABORTED = "WifiNanRangingListenerOnAborted"
NETWORK_CALLBACK = "NetworkCallback"
DATA_PATH_INITIATOR = 0
DATA_PATH_RESPONDER = 1

WIFI_MAX_TX_RETRIES = 5


class WifiNanManagerTest(base_test.BaseTestClass):
    def setup_test(self):
        for ad in self.android_devices:
            asserts.assert_true(
                wutils.wifi_toggle_state(ad, True),
                "Failed enabling Wi-Fi interface")
            nan_usage_enabled = ad.droid.wifiIsNanUsageEnabled()
            if not nan_usage_enabled:
                self.log.info('NAN not enabled. Waiting for %s',
                              WIFI_NAN_ENABLED)
                try:
                    ad.ed.pop_event(WIFI_NAN_ENABLED, 10)
                    self.log.info(WIFI_NAN_ENABLED)
                except queue.Empty:
                    asserts.fail('Timed out while waiting for %s' %
                                 WIFI_NAN_ENABLED)

    # def teardown_test(self):
    #     for ad in self.android_devices:
    #         ad.droid.wifiNanDisconnect()
    #         asserts.assert_true(
    #             wutils.wifi_toggle_state(ad, False),
    #             "Failed disabling Wi-Fi interface")

    def get_interface_mac(self, device, interface):
        """Get the HW MAC address of the specified interface.

        Returns the HW MAC address or raises an exception on failure.

        Args:
            device: The 'AndroidDevice' on which to query the interface.
            interface: The name of the interface to query.

        Returns:
            mac: MAC address of the interface.
        """
        out = device.adb.shell("ifconfig %s" % interface)
        completed = out.decode('utf-8').strip()
        res = re.match(".* HWaddr (\S+).*", completed, re.S)
        asserts.assert_true(res, 'Unable to obtain MAC address for interface %s'
                            % interface)
        return res.group(1)

    def get_interface_ipv6_link_local(self, device, interface):
        """Get the link-local IPv6 address of the specified interface.

        Returns the link-local IPv6 address of the interface or raises an
        exception on failure.

        Args:
            device: The 'AndroidDevice' on which to query the interface.
            interface: The name of the interface to query.

        Returns:
            addr: link-local IPv6 address of the interface.
        """
        out = device.adb.shell("ifconfig %s" % interface)
        completed = out.decode('utf-8').strip()
        res = re.match(".*inet6 addr: (\S+)/64 Scope: Link.*", completed, re.S)
        asserts.assert_true(res,
                            'Unable to obtain IPv6 link-local for interface %s'
                            % interface)
        return res.group(1)

    def exec_connect(self, device, config_request, name):
        """Executes the NAN connection creation operation.

        Creates a NAN connection (client) and waits for a confirmation event
        of success. Raise test failure signal if no such event received.

        Args:
            device: The 'AndroidDevice' on which to set up the connection.
            config_request: The configuration of the connection.
            name: An arbitary name used for logging.
        """
        device.droid.wifiNanConnect(config_request)
        try:
            event = device.ed.pop_event(ON_CONNECT_SUCCESS, 30)
            self.log.info('%s: %s', ON_CONNECT_SUCCESS, event['data'])
        except queue.Empty:
            asserts.fail('Timed out while waiting for %s on %s' %
                         (ON_CONNECT_SUCCESS, name) )
        self.log.debug(event)

    def reliable_tx(self, device, session_id, peer, msg):
        """Sends a NAN message.

        Sends a message to the peer and waits for success confirmation. Raises
        an exception on failure or timeout.

        The message is sent using the MAX retransmission count.

        Args:
            device: The 'AndroidDevice' on which to send the message.
            session_id: The session ID context from which to send the message.
                This is the value returned by wifiNanPublish() or
                wifiNanSubscribe().
            peer: The peer ID to send the message to. Obtained through a match
                or a received message.
            msg: The message to be transmitted to the peer.
        """
        events_regex = '%s|%s' % (ON_MESSAGE_TX_FAIL, ON_MESSAGE_TX_OK)
        self.msg_id = self.msg_id + 1

        while True:
            try:
                device.droid.wifiNanSendMessage(session_id, peer, msg,
                                                self.msg_id,
                                                WIFI_MAX_TX_RETRIES)
                events = device.ed.pop_events(events_regex, 30)
            except queue.Empty:
                asserts.fail('Timed out while waiting for %s', events_regex)

            for event in events:
                self.log.info('%s: %s', event['name'], event['data'])
                if event['data']['messageId'] == self.msg_id:
                    asserts.assert_equal(event['name'], ON_MESSAGE_TX_OK,
                                        'Failed (re)transmission')
                    return

    def exec_rtt(self, device, session_id, peer_id, rtt_param):
        """Executes an RTT operation.

        Args:
            device: The 'AndroidDevice' on which to send the message.
            session_id: The session ID context from which to send the message.
                This is the value returned by wifiNanPublish() or
                wifiNanSubscribe().
            peer_id: The peer ID to send the message to. Obtained through a
                match or a received message.
            rtt_param: RTT session parameters.
        """
        rtt_param['bssid'] = peer_id
        device.droid.wifiNanStartRanging(0, session_id, [rtt_param])

        events_regex = '%s|%s|%s' % (ON_RANGING_SUCCESS, ON_RANGING_FAILURE,
                                     ON_RANGING_ABORTED)
        try:
            events_pub_range = device.ed.pop_events(events_regex, 30)
            for event in events_pub_range:
                self.log.info('%s: %s', event['name'], event['data'])
        except queue.Empty:
            self.log.info('Timed out while waiting for RTT events %s',
                          events_regex)

    def test_nan_discovery_session(self):
        """Perform NAN configuration, discovery, and message exchange.

        Configuration: 2 devices, one acting as Publisher (P) and the
        other as Subscriber (S)

        Logical steps:
          * P & S connect to NAN
          * P & S wait for NAN connection confirmation
          * P starts publishing
          * S starts subscribing
          * S waits for a match (discovery) notification
          * S sends a message to P, confirming that sent successfully
          * P waits for a message and confirms that received (uncorrupted)
          * P sends a message to S, confirming that sent successfully
          * S waits for a message and confirms that received (uncorrupted)
        """
        # Configure Test
        self.publisher = self.android_devices[0]
        self.subscriber = self.android_devices[1]
        required_params = ("config_request1", "config_request2",
                           "publish_config", "subscribe_config")
        self.unpack_userparams(required_params)
        self.msg_id = 10

        sub2pub_msg = "How are you doing?"
        pub2sub_msg = "Doing ok - thanks!"

        # Start Test
        self.exec_connect(self.publisher, self.config_request1, "publisher")
        self.exec_connect(self.subscriber, self.config_request2, "subscriber")

        pub_id = self.publisher.droid.wifiNanPublish(0, self.publish_config)
        sub_id = self.subscriber.droid.wifiNanSubscribe(0,
                                                        self.subscribe_config)

        try:
            event_sub_match = self.subscriber.ed.pop_event(ON_MATCH, 30)
            self.log.info('%s: %s', ON_MATCH, event_sub_match['data'])
        except queue.Empty:
            asserts.fail('Timed out while waiting for %s on Subscriber' %
                         ON_MATCH)
        self.log.debug(event_sub_match)

        self.reliable_tx(self.subscriber, sub_id,
                         event_sub_match['data']['peerId'], sub2pub_msg)

        try:
            event_pub_rx = self.publisher.ed.pop_event(ON_MESSAGE_RX, 10)
            self.log.info('%s: %s', ON_MESSAGE_RX, event_pub_rx['data'])
            asserts.assert_equal(event_pub_rx['data']['messageAsString'],
                                 sub2pub_msg,
                                 "Subscriber -> publisher message corrupted")
        except queue.Empty:
            asserts.fail('Timed out while waiting for %s on publisher' %
                         ON_MESSAGE_RX)

        self.reliable_tx(self.publisher, pub_id, event_pub_rx['data']['peerId'],
                         pub2sub_msg)

        try:
            event_sub_rx = self.subscriber.ed.pop_event(ON_MESSAGE_RX, 10)
            self.log.info('%s: %s', ON_MESSAGE_RX, event_sub_rx['data'])
            asserts.assert_equal(event_sub_rx['data']['messageAsString'],
                                 pub2sub_msg,
                                 "Publisher -> subscriber message corrupted")
        except queue.Empty:
            asserts.fail('Timed out while waiting for %s on subscriber' %
                         ON_MESSAGE_RX)

        self.publisher.droid.wifiNanTerminateSession(pub_id)
        self.subscriber.droid.wifiNanTerminateSession(sub_id)

    def test_nan_rtt(self):
        """Perform NAN configuration, discovery, and RTT.

        Configuration: 2 devices, one acting as Publisher (P) and the
        other as Subscriber (S)

        Logical steps:
          * P & S connect to NAN
          * P & S wait for NAN connection confirmation
          * P starts publishing
          * S starts subscribing
          * S waits for a match (discovery) notification
          * S performs 3 RTT measurements with P
        """
        # Configure Test
        self.publisher = self.android_devices[0]
        self.subscriber = self.android_devices[1]
        required_params = ("config_request1", "config_request2",
                           "publish_config", "subscribe_config", "rtt_24_20",
                           "rtt_50_40", "rtt_50_80")
        self.unpack_userparams(required_params)

        # Start Test
        self.exec_connect(self.publisher, self.config_request1, "publisher")
        self.exec_connect(self.subscriber, self.config_request2, "subscriber")

        pub_id = self.publisher.droid.wifiNanPublish(0, self.publish_config)
        sub_id = self.subscriber.droid.wifiNanSubscribe(0,
                                                        self.subscribe_config)

        try:
            event_sub_match = self.subscriber.ed.pop_event(ON_MATCH, 30)
            self.log.info('%s: %s', ON_MATCH, event_sub_match['data'])
        except queue.Empty:
            asserts.fail('Timed out while waiting for %s on Subscriber' %
                         ON_MATCH)
        self.log.debug(event_sub_match)

        self.exec_rtt(self.subscriber, sub_id,
                      event_sub_match['data']['peerId'], self.rtt_24_20)
        self.exec_rtt(self.subscriber, sub_id,
                      event_sub_match['data']['peerId'], self.rtt_50_40)
        self.exec_rtt(self.subscriber, sub_id,
                      event_sub_match['data']['peerId'], self.rtt_50_80)

    def test_disable_wifi_during_connection(self):
        """Validate behavior when Wi-Fi is disabled during an active NAN
        connection. Expected behavior: receive an onNanDown(1002) event.

        Configuration: 1 device - the DUT.

        Logical steps:
          * DUT connect to NAN
          * DUT waits for NAN connection confirmation
          * DUT starts publishing
          * Disable Wi-Fi
          * DUT waits for an onNanDown(1002) event and confirms that received
        """
        # Configure Test
        self.dut = self.android_devices[0]
        required_params = ("config_request1", "publish_config")
        self.unpack_userparams(required_params)

        # Start Test
        self.dut.droid.wifiNanConnect(self.config_request1)

        try:
            event = self.dut.ed.pop_event(ON_CONNECT_SUCCESS, 30)
            self.log.info('%s: %s', ON_CONNECT_SUCCESS, event['data'])
        except queue.Empty:
            asserts.fail('Timed out while waiting for %s on dut' %
                         ON_CONNECT_SUCCESS)
        self.log.debug(event)

        pub_id = self.dut.droid.wifiNanPublish(0, self.publish_config)

        asserts.assert_true(
            wutils.wifi_toggle_state(self.dut, False),
            "Failed disabling Wi-Fi interface on dut")

        try:
            event = self.dut.ed.pop_event(WIFI_NAN_DISABLED, 30)
            self.log.info(WIFI_NAN_DISABLED)
        except queue.Empty:
            asserts.fail('Timed out while waiting for %s on dut' %
                         WIFI_NAN_DISABLED)
        self.log.debug(event)

    def test_nan_data_path(self):
        """Perform NAN configuration, discovery, data-path setup, and data
        transfer.

        Configuration: 2 devices, one acting as Publisher (P) and the
        other as Subscriber (S)

        Logical steps:
          * P & S connect to NAN
          * P & S wait for NAN connection confirmation
          * P starts publishing
          * S starts subscribing
          * S waits for a match (discovery) notification
          * S sends a message to P
          * P waits for message
          * P creates a NAN network to S as RESPONDER
          * P sends a message to S
          * S waits for message
          * S creates a NAN network to P as INITIATOR (order important!)
          * Both P & S wait for events confirming network set up
          * manually configure neighbor address for peer on P and S
          * run iperf3 between P (server) and S (client)
          * unregister network callback on S
        """
        # Configure Test
        self.publisher = self.android_devices[0]
        self.subscriber = self.android_devices[1]
        required_params = ("config_request1", "config_request2",
                           "publish_config", "subscribe_config", "network_req",
                           "nan_interface")
        self.unpack_userparams(required_params)
        self.msg_id = 10

        nan0 = self.nan_interface["NanInterface"]
        sub2pub_msg = "Get ready!"
        pub2sub_msg = "Ready!"
        test_token = "Token / <some magic string>"

        # Start Test
        self.exec_connect(self.publisher, self.config_request1, "publisher")
        self.exec_connect(self.subscriber, self.config_request2, "subscriber")

        pub_id = self.publisher.droid.wifiNanPublish(0, self.publish_config)
        sub_id = self.subscriber.droid.wifiNanSubscribe(0,
                                                        self.subscribe_config)

        try:
            event_sub_match = self.subscriber.ed.pop_event(ON_MATCH, 30)
            self.log.info('%s: %s', ON_MATCH, event_sub_match['data'])
        except queue.Empty:
            asserts.fail('Timed out while waiting for %s on Subscriber' %
                         ON_MATCH)
        self.log.debug(event_sub_match)

        self.reliable_tx(self.subscriber, sub_id,
                         event_sub_match['data']['peerId'], sub2pub_msg)

        try:
            event_pub_rx = self.publisher.ed.pop_event(ON_MESSAGE_RX, 10)
        except queue.Empty:
            asserts.fail('Timed out while waiting for %s on publisher' %
                         ON_MESSAGE_RX)
        self.log.info('%s: %s', ON_MESSAGE_RX, event_pub_rx['data'])
        asserts.assert_equal(event_pub_rx['data']['messageAsString'],
                             sub2pub_msg,
                             "Subscriber -> publisher message corrupted")

        pub_ns = self.publisher.droid.wifiNanCreateNetworkSpecifier(
            DATA_PATH_RESPONDER, pub_id, event_pub_rx['data']['peerId'],
            test_token)
        self.log.info("Publisher network specifier - '%s'", pub_ns)
        self.network_req['NetworkSpecifier'] = pub_ns
        pub_req_key = self.publisher.droid.connectivityRequestNetwork(
            self.network_req)

        self.reliable_tx(self.publisher, pub_id, event_pub_rx['data']['peerId'],
                         pub2sub_msg)

        try:
            event_sub_rx = self.subscriber.ed.pop_event(ON_MESSAGE_RX, 10)
        except queue.Empty:
            asserts.fail('Timed out while waiting for %s on subscriber' %
                         ON_MESSAGE_RX)
        self.log.info('%s: %s', ON_MESSAGE_RX, event_sub_rx['data'])
        asserts.assert_equal(event_sub_rx['data']['messageAsString'],
                             pub2sub_msg,
                             "Publisher -> subscriber message corrupted")

        sub_ns = self.subscriber.droid.wifiNanCreateNetworkSpecifier(
            DATA_PATH_INITIATOR, sub_id, event_sub_rx['data']['peerId'],
            test_token)
        self.log.info("Subscriber network specifier - '%s'", sub_ns)
        self.network_req['NetworkSpecifier'] = sub_ns
        sub_req_key = self.subscriber.droid.connectivityRequestNetwork(
            self.network_req)

        try:
            event_network = self.subscriber.ed.pop_event(NETWORK_CALLBACK, 30)
            self.log.info('Subscriber %s: %s', NETWORK_CALLBACK,
                          event_network['data'])
        except queue.Empty:
            asserts.fail('Timed out while waiting for %s on Subscriber' %
                         NETWORK_CALLBACK)
        self.log.debug(event_network)

        try:
            event_network = self.publisher.ed.pop_event(NETWORK_CALLBACK, 30)
            self.log.info('Publisher %s: %s', NETWORK_CALLBACK,
                          event_network['data'])
        except queue.Empty:
            asserts.fail('Timed out while waiting for %s on Publisher' %
                         NETWORK_CALLBACK)
        self.log.debug(event_network)

        pub_ipv6 = self.get_interface_ipv6_link_local(self.publisher, nan0)
        self.log.debug("Publisher IPv6 link-local %s", pub_ipv6)

        result, data = self.publisher.run_iperf_server("-D")
        asserts.assert_true(result, "Can't start iperf3 server")

        result, data = self.subscriber.run_iperf_client(
            "%s%%%s" % (pub_ipv6, nan0), "-6 -J")
        self.log.debug(data)
        asserts.assert_true(result,
                            "Failure starting/running iperf3 in client mode")
        self.log.debug(pprint.pformat(data))
        data_json = json.loads(''.join(data))
        self.log.info('iPerf3: Sent = %d bps Received = %d bps',
                      data_json['end']['sum_sent']['bits_per_second'],
                      data_json['end']['sum_received']['bits_per_second'])

        self.subscriber.droid.connectivityUnregisterNetworkCallback(sub_req_key)
