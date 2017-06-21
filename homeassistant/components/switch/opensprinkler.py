"""
Support for OpenSprinkler.

Only tested on firmware 2.1.7
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_TIMEOUT)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['python-opensprinkler==0.1.22']

_LOGGER = logging.getLogger(__name__)

# Currently no https support.  Author recommends reverse proxy.
# Alternate ports should use something like:  host = "123.123.123.123:8880"
# Duration is 0-64800 (18 hours)

CONF_RUNTIME = 'default_runtime'
CONF_REFRESH = 'full_refresh'
CONF_RETRIES = 'retries'

DEFAULT_NAME = 'OpenSprinkler'
DEFAULT_PASSWORD = 'opendoor'
DEFAULT_STATIONRUNTIME = 600
DEFAULT_REFRESH = 300
DEFAULT_RETRIES = 5
DEFAULT_TIMEOUT = 20

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_RUNTIME, default=DEFAULT_STATIONRUNTIME):
        vol.All(vol.Coerce(int), vol.Range(min=1, max=64800)),
    vol.Optional(CONF_REFRESH, default=DEFAULT_REFRESH):
        vol.All(vol.Coerce(int), vol.Range(min=1, max=600)),
    vol.Optional(CONF_RETRIES, default=DEFAULT_RETRIES):
        vol.All(vol.Coerce(int), vol.Range(min=1, max=600)),
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT):
        vol.All(vol.Coerce(int), vol.Range(min=1, max=600)),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return OpenSprinkler device."""
    import opensprinkler

    host = config.get(CONF_HOST)
    controllername = config.get(CONF_NAME)
    pswd = config.get(CONF_PASSWORD)
    tout = config.get(CONF_TIMEOUT)
    runtime = config.get(CONF_RUNTIME)
    refresh = config.get(CONF_REFRESH)
    retries = config.get(CONF_RETRIES)

    sprinkler_device = opensprinkler.OSDevice(
        hostname=host, password=pswd, timeout=tout,
        defaultstationruntime=runtime, fulldatarefresh=refresh,
        maxretries=retries
    )


    if not sprinkler_device.verify():
        _LOGGER.error('Could not connect to OpenSprinkler')
        return False

    stations = []
    parent_device = OpenSprinklerDevice(sprinkler_device)

    stations.extend(
        OpenSprinklerStation(controllername, item.station_number,
        parent_device)
        for item in sprinkler_device
    )

    add_devices(stations)


class OpenSprinklerStation(SwitchDevice):
    """Representation of a individual OpenSprinkler Station."""

    def __init__(self, name, stationnumber, parent_device):
        """Initialize the OpenSprinkler station."""
        self._parent_device = parent_device
        self.controllername = name
        self.stationnumber = stationnumber
        self.update()

    @property
    def name(self):
        """Return the display name of this relay."""
        return self._outletname

    @property
    def is_on(self):
        """Return true if relay is on."""
        return self._is_on

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    def turn_on(self, **kwargs):
        """Instruct the relay to turn on."""
        self._parent_device.turn_on(station=self.stationnumber-1)

    def turn_off(self, **kwargs):
        """Instruct the relay to turn off."""
        self._parent_device.turn_off(station=self.stationnumber-1)

    def update(self):
        """Trigger update for all switches on the parent device."""
        self._parent_device.update()
        self._is_on = (
            self._parent_device.statuslocal[self.stationnumber - 1][2] == 'ON'
        )
        self._outletname = "{}_{}".format(
            self.controllername,
            self._parent_device.statuslocal[self.stationnumber - 1][1]
        )


class OpenSprinklerDevice(object):
    """Device representation for per device throttling."""

    def __init__(self, device):
        """Initialize the OpenSprinkler device."""
        self._device = device
        self.update()

    def turn_on(self, **kwargs):
        """Instruct the relay to turn on."""
        self._device.on(**kwargs)

    def turn_off(self, **kwargs):
        """Instruct the relay to turn off."""
        self._device.off(**kwargs)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for this device."""
        self.statuslocal = self._device.statuslist()
