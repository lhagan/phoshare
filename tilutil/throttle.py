"""Execution Throttle."""

# Copyright 2010 Google Inc.
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

class Throttle(object):
    """Throttle for placing calls to not exceed a per second rate.
    
    Does not track calls over time, but only ensures that two subsequent
    calls do not exceed the rate."""
    
    def __init__(self, per_second_rate):
        """Constructs a throttle. The first call to throttle() will not be
        delayed.
        
        Args:
          perSecondRate: maximum number of throttle() calls allowed per second.
        """
        if per_second_rate <= 0.0:
            raise ValueError('Rate must be greater than 0.')
        self.delay = 1.0 / per_second_rate
        self.next_start_time = time.time()

    def throttle(self):
        """Block the caller until enough time since the last throttle() call 
        has elapsed to ensure that the declare perSecondRate is not exceeded. 
        Call this method before any code that needs to be rate limited.
        """
        if self.delay <= 0.0:
            return
        while True:
            diff = self.next_start_time - time.time()
            if diff <= 0.0:
                break
            time.sleep(diff)
        self.next_start_time = time.time() + self.delay
