"""Device tracker platform that adds support for Leaf Spy."""
import logging

from homeassistant.core import callback
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_BATTERY_LEVEL,
    # ATTR_BATTERY_HEALTH,
    # ATTR_BATTERY_CONDUCTANCE,
)
from homeassistant.components.device_tracker.const import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import (
    TrackerEntity
)
from homeassistant.util import slugify
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers import device_registry
from .const import DOMAIN as LS_DOMAIN

_LOGGER = logging.getLogger(__name__)

PLUG_STATES = [
    "Not Plugged In",
    "Partially Plugged In",
    "Plugged In"
]

CHARGE_MODES = [
    "Not Charging",
    "Level 1 Charging (100-120 Volts)",
    "Level 2 Charging (200-240 Volts)",
    "Level 3 Quick Charging"
]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Leaf Spy based off an entry."""
    async def _receive_data(dev_id, **data):
        """Receive set location."""
        entity = hass.data[LS_DOMAIN]['devices'].get(dev_id)

        if entity is not None:
            entity.update_data(data)
            return

        entity = hass.data[LS_DOMAIN]['devices'][dev_id] = LeafSpyEntity(
            dev_id, data
        )
        async_add_entities([entity])

    hass.data[LS_DOMAIN]['context'].set_async_see(_receive_data)

    # Restore previously loaded devices
    dev_reg = await device_registry.async_get_registry(hass)
    dev_ids = {
        identifier[1]
        for device in dev_reg.devices.values()
        for identifier in device.identifiers
        if identifier[0] == LS_DOMAIN
    }

    if not dev_ids:
        return

    entities = []
    for dev_id in dev_ids:
        entity = hass.data[LS_DOMAIN]['devices'][dev_id] = LeafSpyEntity(
            dev_id
        )
        entities.append(entity)

    async_add_entities(entities)


class LeafSpyEntity(TrackerEntity, RestoreEntity):
    """Represent a tracked car."""

    def __init__(self, dev_id, data=None):
        """Set up LeafSpy entity."""
        self._dev_id = dev_id
        self._data = data or {}
        self.entity_id = f"{LS_DOMAIN}.{dev_id}"

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._dev_id

    @property
    def battery_level(self):
        """Return the battery level of the car."""
        return self._data.get('battery_level')

    # @property
    # def battery_health(self):
    #     """Return the battery health of the car."""
    #     return self._data.get('battery_health')

    # @property
    # def battery_conductance(self):
    #     """Return the battery conductance of the car."""
    #     return self._data.get('battery_conductance')

    @property
    def device_state_attributes(self):
        """Return device specific attributes."""
        return self._data.get('attributes')

    @property
    def latitude(self):
        """Return latitude value of the car."""
        return self._data.get('latitude')

    @property
    def longitude(self):
        """Return longitude value of the car."""
        return self._data.get('longitude')

    @property
    def name(self):
        """Return the name of the car."""
        return self._data.get('device_name')

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def source_type(self):
        """Return the source type of the car."""
        return SOURCE_TYPE_GPS

    @property
    def device_info(self):
        """Return the device info."""
        return {
            'name': self.name,
            'identifiers': {(LS_DOMAIN, self._dev_id)},
        }

    async def async_added_to_hass(self):
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()

        # Don't restore if we got set up with data.
        if self._data:
            return

        state = await self.async_get_last_state()

        if state is None:
            return

        attr = state.attributes
        self._data = {
            'device_name': state.name,
            'latitude': attr.get(ATTR_LATITUDE),
            'longitude': attr.get(ATTR_LONGITUDE),
            'battery_level': attr.get(ATTR_BATTERY_LEVEL),
            # 'battery_health': attr.get(ATTR_BATTERY_HEALTH),
            # 'battery_conductance': attr.get(ATTR_BATTERY_CONDUCTANCE),
            'attributes': attr

        }

    @callback
    def update_data(self, data):
        """Mark the device as seen."""
        self._data = data
        self.async_write_ha_state()


def _parse_see_args(message):
    """Parse the Leaf Spy parameters, into the format see expects."""
    dev_id = slugify('leaf_{}'.format(message['VIN']))
    args = {
        'dev_id': dev_id,
        'device_name': message['user'],
        'latitude': float(message['Lat']),
        'longitude': float(message['Long']),
        'battery_level': float(message['SOC']),
        # 'battery_health': float(message['SOH']),
        # 'battery_conductance': float(message['Hx']),
        'attributes': {
            'amp_hours': float(message['AHr']),
            'trip': int(message['Trip']),
            'odometer': int(message['Odo']),
            'battery_temperature': float(message['BatTemp']),
            'outside_temperature': float(message['Amb']),
            'plug_state': PLUG_STATES[int(message['PlugState'])],
            'charge_mode': CHARGE_MODES[int(message['ChrgMode'])],
            'charge_power': int(message['ChrgPwr']),
            'vin': message['VIN'],
            'power_switch': message['PwrSw'] == '1',
            'device_battery': int(message['DevBat']),
            'rpm': int(message['RPM']),
            'gids': int(message['Gids']),
            'elevation': float(message['Elv']),
            'sequence': int(message['Seq']),
            'wiper_status': int(message['Wpr'])
        }
    }

    return args


async def async_handle_message(hass, context, message):
    """Handle an Leaf Spy message."""
    _LOGGER.debug("Received %s", message)

    args = _parse_see_args(message)
    await context.async_see(**args)
