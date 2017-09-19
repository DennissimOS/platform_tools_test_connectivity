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


######################################################
# RangingResultCallback events
######################################################
EVENT_CB_RANGING_ON_FAIL = "WifiRttRangingFailure"
EVENT_CB_RANGING_ON_RESULT = "WifiRttRangingResults"

EVENT_CB_RANGING_KEY_RESULTS = "Results"

EVENT_CB_RANGING_KEY_STATUS = "status"
EVENT_CB_RANGING_KEY_DISTANCE_CM = "distanceCm"
EVENT_CB_RANGING_KEY_DISTANCE_STD_DEV_CM = "distanceStdDevCm"
EVENT_CB_RANGING_KEY_RSSI = "rssi"
EVENT_CB_RANGING_KEY_TIMESTAMP = "timestamp"
EVENT_CB_RANGING_KEY_MAC = "mac"
EVENT_CB_RANGING_KEY_MAC_AS_STRING = "macAsString"

EVENT_CB_RANGING_STATUS_SUCCESS = 0

######################################################
# ScanResults keys
######################################################

SCAN_RESULT_KEY_RTT_RESPONDER = "is80211McRTTResponder"