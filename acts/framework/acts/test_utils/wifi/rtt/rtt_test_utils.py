#!/usr/bin/env python3.4
#
#   Copyright 2017 - Google
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

import queue
import statistics

from acts import asserts
from acts.test_utils.wifi import wifi_test_utils as wutils
from acts.test_utils.wifi.rtt import rtt_const as rconsts

# arbitrary timeout for events
EVENT_TIMEOUT = 10


def decorate_event(event_name, id):
  return '%s_%d' % (event_name, id)


def wait_for_event(ad, event_name, timeout=EVENT_TIMEOUT):
  """Wait for the specified event or timeout.

  Args:
    ad: The android device
    event_name: The event to wait on
    timeout: Number of seconds to wait
  Returns:
    The event (if available)
  """
  prefix = ''
  if hasattr(ad, 'pretty_name'):
    prefix = '[%s] ' % ad.pretty_name
  try:
    event = ad.ed.pop_event(event_name, timeout)
    ad.log.info('%s%s: %s', prefix, event_name, event['data'])
    return event
  except queue.Empty:
    ad.log.info('%sTimed out while waiting for %s', prefix, event_name)
    asserts.fail(event_name)


def get_rtt_supporting_networks(scanned_networks):
  """Filter the input list and only return those networks which support
    802.11mc.

    Args:
      scanned_networks: A list of networks from scan results.

    Returns: a sub-set of the scanned_networks which support 802.11mc.
    """
  rtt_networks = []
  for network in scanned_networks:
    if (rconsts.SCAN_RESULT_KEY_RTT_RESPONDER in network and
        network[rconsts.SCAN_RESULT_KEY_RTT_RESPONDER]):
      rtt_networks.append(network)

  return rtt_networks


def scan_networks(dut):
  """Perform a scan and return scan results.

    Args:
      dut: Device under test.

    Returns: an array of scan results.
    """
  wutils.start_wifi_connection_scan(dut)
  return dut.droid.wifiGetScanResults()


def scan_for_rtt_supporting_networks(dut, repeat=0):
  """Perform a scan and return scan results.

    Args:
      dut: Device under test.
      repeat: Re-scan this many times to find an RTT supporting network.

    Returns: an array of scan results.
    """
  for i in range(repeat + 1):
    wutils.start_wifi_connection_scan(dut)
    scan_results = dut.droid.wifiGetScanResults()
    rtt_aps = get_rtt_supporting_networks(scan_results)
    if len(rtt_aps) != 0:
      return rtt_aps

  return []


def validate_ap_result(scan_result, range_result):
  """Validate the range results:
  - Successful if AP (per scan result) support 802.11mc (allowed to fail
    otherwise)
  - MAC of result matches the BSSID

  Args:
    scan_result: Scan result for the AP
    range_result: Range result returned by the RTT API
  """
  asserts.assert_equal(scan_result[wutils.WifiEnums.BSSID_KEY], range_result[
    rconsts.EVENT_CB_RANGING_KEY_MAC_AS_STRING_BSSID], 'MAC/BSSID mismatch')
  if (rconsts.SCAN_RESULT_KEY_RTT_RESPONDER in scan_result and
      scan_result[rconsts.SCAN_RESULT_KEY_RTT_RESPONDER]):
    asserts.assert_true(range_result[rconsts.EVENT_CB_RANGING_KEY_STATUS] ==
                        rconsts.EVENT_CB_RANGING_STATUS_SUCCESS,
                        'Ranging failed for an AP which supports 802.11mc!')


def validate_ap_results(scan_results, range_results):
  """Validate an array of ranging results against the scan results used to
  trigger the range. The assumption is that the results are returned in the
  same order as the request (which were the scan results).

  Args:
    scan_results: Scans results used to trigger the range request
    range_results: Range results returned by the RTT API
  """
  asserts.assert_equal(
      len(scan_results),
      len(range_results),
      'Mismatch in length of scan results and range results')

  # sort first based on BSSID/MAC
  scan_results.sort(key=lambda x: x[wutils.WifiEnums.BSSID_KEY])
  range_results.sort(
      key=lambda x: x[rconsts.EVENT_CB_RANGING_KEY_MAC_AS_STRING_BSSID])

  for i in range(len(scan_results)):
    validate_ap_result(scan_results[i], range_results[i])


def validate_aware_mac_result(range_result, mac, description):
  """Validate the range result for An Aware peer specified with a MAC address:
  - Correct MAC address

  Args:
    range_result: Range result returned by the RTT API
    mac: MAC address of the peer
    description: Additional content to print on failure
  """
  asserts.assert_equal(mac,
                       range_result[rconsts.EVENT_CB_RANGING_KEY_MAC_AS_STRING],
                       '%s: MAC mismatch' % description)

def validate_aware_peer_id_result(range_result, peer_id, description):
  """Validate the range result for An Aware peer specified with a Peer ID:
  - Correct Peer ID
  - MAC address information not available

  Args:
    range_result: Range result returned by the RTT API
    peer_id: Peer ID of the peer
    description: Additional content to print on failure
  """
  asserts.assert_equal(peer_id,
                       range_result[rconsts.EVENT_CB_RANGING_KEY_PEER_ID],
                       '%s: Peer Id mismatch' % description)
  asserts.assert_false(rconsts.EVENT_CB_RANGING_KEY_MAC in range_result,
                       '%s: MAC Address not empty!' % description)


def extract_stats(events, range_reference_mm, range_margin, max_rssi):
  """Extract statistics from a list of RTT result events. Returns a dictionary
   with results:
     - num_samples
     - num_no_results (e.g. timeout)
     - num_failures
     - num_range_out_of_margin (only for successes)
     - num_invalid_rssi (only for successes)
     - distances: extracted list of distances
     - distance_std_devs: extracted list of distance standard-deviations
     - rssis: extracted list of RSSI
     - distance_mean
     - distance_std_dev (based on distance - ignoring the individual std-devs)
     - rssi_mean
     - rssi_std_dev
     - status_codes

  Args:
    events: List of RTT result events.
    range_reference_mm: Reference value for the distance (in mm)
    range_margin: Acceptable margin for distance (in % of reference)
    max_rssi: Acceptable maximum RSSI value.

  Returns: A dictionary of stats.
  """
  stats = {}
  stats['num_results'] = len(events)
  stats['num_no_results'] = 0
  stats['num_failures'] = 0
  stats['num_range_out_of_margin'] = 0
  stats['num_invalid_rssi'] = 0

  range_max_mm = range_reference_mm * (100 + range_margin) / 100
  range_min_mm = range_reference_mm * (100 - range_margin) / 100

  distances = []
  distance_std_devs = []
  rssis = []
  status_codes = []

  for i in range(len(events)):
    event = events[i]

    if event is None: # None -> timeout waiting for RTT result
      stats['num_no_results'] = stats['num_no_results'] + 1
      continue

    results = event["data"][rconsts.EVENT_CB_RANGING_KEY_RESULTS][0]
    status_codes.append(results[rconsts.EVENT_CB_RANGING_KEY_STATUS])
    if status_codes[-1] != rconsts.EVENT_CB_RANGING_STATUS_SUCCESS:
      stats['num_failures'] = stats['num_failures'] + 1
      continue

    distance_mm = results[rconsts.EVENT_CB_RANGING_KEY_DISTANCE_MM]
    distances.append(distance_mm)
    if not range_min_mm <= distance_mm <= range_max_mm:
      stats['num_range_out_of_margin'] = stats['num_range_out_of_margin'] + 1
    distance_std_devs.append(
        results[rconsts.EVENT_CB_RANGING_KEY_DISTANCE_STD_DEV_MM])

    rssi = results[rconsts.EVENT_CB_RANGING_KEY_RSSI]
    rssis.append(rssi)
    if not 0 <= rssi <= max_rssi:
      stats['num_invalid_rssi'] = stats['num_invalid_rssi'] + 1

  stats['distances'] = distances
  if len(distances) > 0:
    stats['distance_mean'] = statistics.mean(distances)
  if len(distances) > 1:
    stats['distance_std_dev'] = statistics.stdev(distances)
  stats['distance_std_devs'] = distance_std_devs
  stats['rssis'] = rssis
  if len(rssis) > 0:
    stats['rssi_mean'] = statistics.mean(rssis)
  if len(rssis) > 1:
    stats['rssi_std_dev'] = statistics.stdev(rssis)
  stats['status_codes'] = status_codes

  return stats