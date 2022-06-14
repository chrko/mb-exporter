import asyncio
import json
import logging
import math
from abc import ABC, abstractmethod
from enum import Enum
from http import HTTPStatus as codes
from typing import Optional

from oauthlib.oauth2 import MismatchingStateError
from prometheus_client import Gauge
from requests import Response
from requests_oauthlib import OAuth2Session

logger = logging.getLogger(__name__)


class MbCustomer(OAuth2Session):
    AUTHORIZATION_URL = "https://id.mercedes-benz.com/as/authorization.oauth2"
    TOKEN_URL = "https://id.mercedes-benz.com/as/token.oauth2"

    def __init__(self, client_id: str, client_secret: str):
        super().__init__(
            client_id=client_id,
            scope=[
                "offline_access",
                "mb:vehicle:mbdata:evstatus",
                "mb:vehicle:mbdata:fuelstatus",
                "mb:vehicle:mbdata:payasyoudrive",
                "mb:vehicle:mbdata:vehiclelock",
                "mb:vehicle:mbdata:vehiclestatus",
            ],
            auto_refresh_url=self.TOKEN_URL,
            token_updater=self._update_token,
            redirect_uri="http://localhost:8080/oauth.redirect",
        )
        self.__client_secret = str(client_secret)
        self.__async_lock = asyncio.Lock()

        try:
            self.restore()
        except Exception as e:
            logger.warning("Error during restoring the token on init: %s", e)

    def _update_token(self, token):
        self.token = token
        try:
            self.persist()
        except Exception as e:
            logger.error("Error during persisting the updated token: %s", e)

    def persist(self):
        with open("state.json", mode="w") as f:
            json.dump(self.token, f, indent=True)

    def restore(self):
        with open("state.json", mode="r") as f:
            self.token = json.load(f)

    def authorization_url(self, **kwargs):
        return super().authorization_url(self.AUTHORIZATION_URL)

    def fetch_token(self, **kwargs):
        if "state" in kwargs and kwargs["state"] != self._state:
            raise MismatchingStateError()
        return super().fetch_token(
            self.TOKEN_URL, client_secret=self.__client_secret, **kwargs
        )

    def refresh_token(self, token_url, **kwargs):
        kwargs["client_id"] = self.client_id
        kwargs["client_secret"] = self.__client_secret
        return super().refresh_token(token_url, **kwargs)

    def request(self, *args, **kwargs):
        if "timeout" not in kwargs:
            kwargs["timeout"] = (5, 30)
        if "headers" not in kwargs:
            kwargs["headers"] = {}
        if "accept" not in kwargs["headers"]:
            kwargs["headers"]["accept"] = "application/json;charset=utf-8"
        return super().request(*args, **kwargs)

    async def request_async(self, *args, **kwargs):
        async with self.__async_lock:
            return await asyncio.to_thread(self.request, *args, **kwargs)

    async def get_async(self, url, **kwargs):
        kwargs.setdefault("allow_redirects", True)
        return await self.request_async("GET", url, **kwargs)

    async def options_async(self, url, **kwargs):
        kwargs.setdefault("allow_redirects", True)
        return await self.request_async("OPTIONS", url, **kwargs)

    async def head_async(self, url, **kwargs):
        kwargs.setdefault("allow_redirects", False)
        return await self.request_async("HEAD", url, **kwargs)

    async def post_async(self, url, data=None, json=None, **kwargs):
        return await self.request_async("POST", url, data=data, json=json, **kwargs)

    async def put_async(self, url, data=None, **kwargs):
        return await self.request_async("PUT", url, data=data, **kwargs)

    async def patch_async(self, url, data=None, **kwargs):
        return await self.request_async("PATCH", url, data=data, **kwargs)

    async def delete_async(self, url, **kwargs):
        return await self.request_async("DELETE", url, **kwargs)


def _kilometers_to_meters(val):
    return float(val) * 1000


def _text_to_bool(val: str):
    return json.loads(val.lower())


def _text_to_bool_not(val: str):
    return not json.loads(val.lower())


class MbPromResRepr(Enum):
    STATE_OF_CHARGE = (
        "soc",
        "mb_electric_state_of_charge",
        "State of Charge obtained from electric vehicle api",
    )
    ELECTRIC_RANGE = (
        "rangeelectric",
        "mb_electric_range",
        "Electric range in kilometers",
        "meters",
        _kilometers_to_meters,
    )

    LIQUID_FUEL_LEVEL = (
        "tanklevelpercent",
        "mb_liquid_fuel_level",
        "Liquid fuel level",
    )
    LIQUID_RANGE = (
        "rangeliquid",
        "mb_liquid_range",
        "Liquid range",
        "meters",
        _kilometers_to_meters,
    )

    ODOMETER = ("odo", "mb_odometer", "Odometer", "meters", _kilometers_to_meters)

    DECK_LID_LOCK_STATUS = (
        "doorlockstatusdecklid",
        "mb_deck_lid_lock_status",
        "Deck lid (Kofferraum) lock status",
        None,
        _text_to_bool_not,
    )
    VEHICLE_LOCK_STATUS = (
        "doorlockstatusvehicle",
        "mb_vehicle_lock_status",
        "Vehicle lock status, 0: vehicle unlocked, 1: vehicle internal locked, 2: vehicle external locked, 3: vehicle selective unlocked",
    )
    GAS_TANK_LOCK_STATUS = (
        "doorlockstatusgas",
        "mb_gas_tank_lock_status",
        "Status of gas tank door lock",
        None,
        _text_to_bool_not,
    )
    VEHICLE_HEADING_POSITION = (
        "positionHeading",
        "mb_vehicle_heading_position",
        "Vehicle heading position",
        "degrees",
    )

    DECK_LID_STATUS = (
        "decklidstatus",
        "mb_deck_lid_open",
        "Deck lid latch status opened/closed state",
        None,
        _text_to_bool,
    )
    DOOR_STATUS_FRONT_LEFT = (
        "doorstatusfrontleft",
        "mb_door_status_front_left",
        "Status of the front left door",
        None,
        _text_to_bool,
    )
    DOOR_STATUS_FRONT_RIGHT = (
        "doorstatusfrontright",
        "mb_door_status_front_right",
        "Status of the front right door",
        None,
        _text_to_bool,
    )
    DOOR_STATUS_REAR_LEFT = (
        "doorstatusrearleft",
        "mb_door_status_rear_left",
        "Status of the rear left door",
        None,
        _text_to_bool,
    )
    DOOR_STATUS_REAR_RIGHT = (
        "doorstatusrearright",
        "mb_door_status_rear_right",
        "Status of the rear right door",
        None,
        _text_to_bool,
    )
    INTERIOR_LIGHTS_FRONT = (
        "interiorLightsFront",
        "mb_interior_front_light_status",
        "Front light inside",
        None,
        _text_to_bool,
    )
    INTERIOR_LIGHTS_REAR = (
        "interiorLightsRear",
        "mb_interior_rear_light_status",
        "Rear light inside",
        None,
        _text_to_bool,
    )
    LIGHT_SWITCH_POSITION = (
        "lightswitchposition",
        "mb_light_switch_position",
        "Light switch position: 0: auto; 1: headlights; 2: sidelight left; 3: sidelight right; 4: parking light",
    )
    READING_LAMP_FRONT_LEFT = (
        "readingLampFrontLeft",
        "mb_reading_lamp_front_left",
        "Front left reading light",
        None,
        _text_to_bool,
    )
    READING_LAMP_FRONT_RIGHT = (
        "readingLampFrontRight",
        "mb_reading_lamp_front_right",
        "Front right reading light",
        None,
        _text_to_bool,
    )
    ROOF_TOP_STATUS = (
        "rooftopstatus",
        "mb_roof_top_status",
        "Status of the convertible top opened/closed: 0: unlocked; 1: open and locked; 2: closed and locked",
    )
    SUN_ROOF_STATUS = (
        "sunroofstatus",
        "mb_sun_roof_status",
        "Status of the sunroof; "
        "0: Tilt/slide sunroof is closed; "
        "1: Tilt/slide sunroof is complete open; "
        "2: Lifting roof is open;"
        "3: Tilt/slide sunroof is running; "
        "4: Tilt/slide sunroof in anti-booming position; "
        "5: Sliding roof in intermediate position;"
        "6: Lifting roof in intermediate position",
    )
    WINDOW_STATUS_FRONT_LEFT = (
        "windowstatusfrontleft",
        "mb_window_status_front_left",
        "Status of the front left window; "
        "0: window in intermediate position; "
        "1: window completely opened; "
        "2: window completely closed; "
        "3: window airing position; "
        "4: window intermediate airing position; "
        "5: window currently running",
    )
    WINDOW_STATUS_FRONT_RIGHT = (
        "windowstatusfrontright",
        "mb_window_status_front_right",
        "Status of the front right window; "
        "0: window in intermediate position; "
        "1: window completely opened; "
        "2: window completely closed; "
        "3: window airing position; "
        "4: window intermediate airing position; "
        "5: window currently running",
    )
    WINDOW_STATUS_REAR_LEFT = (
        "windowstatusrearleft",
        "mb_window_status_rear_left",
        "Status of the rear left window; "
        "0: window in intermediate position; "
        "1: window completely opened; "
        "2: window completely closed; "
        "3: window airing position; "
        "4: window intermediate airing position; "
        "5: window currently running",
    )
    WINDOW_STATUS_REAR_RIGHT = (
        "windowstatusrearright",
        "mb_window_status_rear_right",
        "Status of the rear right window; "
        "0: window in intermediate position; "
        "1: window completely opened; "
        "2: window completely closed; "
        "3: window airing position; "
        "4: window intermediate airing position; "
        "5: window currently running",
    )

    def __init__(
        self,
        resource_name: str,
        metric_base_name: str,
        help_text: str,
        unit_name: Optional[str] = None,
        value_mapper=None,
    ):
        self.resource_name = resource_name

        metric_name = metric_base_name
        if unit_name:
            metric_name += "_" + unit_name

        self.__metric = Gauge(metric_name, help_text, ["vin"])
        self.__measurement_time = Gauge(
            f"{metric_base_name}_measurement_time_seconds",
            f"Measurement time of {metric_name}",
            ["vin"],
        )
        self.__update_time = Gauge(
            f"{metric_base_name}_update_time_seconds",
            f"Update time of {metric_name}",
            ["vin"],
        )
        self.__value_mapper = value_mapper or float

    def new_value(self, vin: str, data: dict):
        self.__metric.labels(vin).set(self.__value_mapper(data["value"]))
        self.__measurement_time.labels(vin).set(data["timestamp"] / 1000)
        self.__update_time.labels(vin).set_to_current_time()

    def no_new_value(self, vin: str):
        self.__update_time.labels(vin).set_to_current_time()


class MbBaseVehicleApi(ABC):
    def __init__(
        self,
        mb_customer: MbCustomer,
        vin: str,
        calls_per_hour: float,
        expected_resources: set,
    ):
        self.mb_customer = mb_customer
        self.vin = str(vin)
        self._calls_per_hour = float(calls_per_hour)
        self.expected_resources = expected_resources

    @abstractmethod
    async def request(self) -> Response:
        ...

    def process_response(self, resp: Response):
        if resp.status_code == codes.NO_CONTENT:
            for v in self.expected_resources:
                v.no_new_value(self.vin)
        elif resp.status_code == codes.OK:
            data = resp.json()
            expected = {v.resource_name: v for v in self.expected_resources}
            for item in data:
                for key in item.keys():
                    if key in expected:
                        expected[key].new_value(self.vin, item[key])
                        del expected[key]
                        break
                    else:
                        logger.warning(f"unexpected resource {key}")

            for value in expected.values():
                value.no_new_value(self.vin)

    async def refresh(self):
        resp = await self.request()
        if resp.status_code in (codes.OK, codes.NO_CONTENT, codes.TOO_MANY_REQUESTS):
            self.process_response(resp)
        else:
            logger.error(
                "Unexpected status code %d during requesting %s. Response text %s",
                resp.status_code,
                resp.request.url,
                resp.text,
            )

    async def continuous_refresh(self):
        while True:
            await self.refresh()
            await asyncio.sleep(math.ceil(3600 / self._calls_per_hour))


class MbElectricVehicleStatus(MbBaseVehicleApi):
    def __init__(self, mb_customer: MbCustomer, vin: str):
        super().__init__(
            mb_customer,
            vin,
            2,
            {MbPromResRepr.ELECTRIC_RANGE, MbPromResRepr.STATE_OF_CHARGE},
        )

    async def request(self) -> Response:
        return await self.mb_customer.get_async(
            f"https://api.mercedes-benz.com/vehicledata/v2/vehicles/{self.vin}/containers/electricvehicle"
        )


class MbFuelStatus(MbBaseVehicleApi):
    def __init__(self, mb_customer: MbCustomer, vin: str):
        super().__init__(
            mb_customer,
            vin,
            1,
            {MbPromResRepr.LIQUID_FUEL_LEVEL, MbPromResRepr.LIQUID_RANGE},
        )

    async def request(self) -> Response:
        return await self.mb_customer.get_async(
            f"https://api.mercedes-benz.com/vehicledata/v2/vehicles/{self.vin}/containers/fuelstatus"
        )


class MbOdometerStatus(MbBaseVehicleApi):
    def __init__(self, mb_customer: MbCustomer, vin: str):
        super().__init__(mb_customer, vin, 1, {MbPromResRepr.ODOMETER})

    async def request(self) -> Response:
        return await self.mb_customer.get_async(
            f"https://api.mercedes-benz.com/vehicledata/v2/vehicles/{self.vin}/containers/payasyoudrive"
        )


class MbVehicleLockStatus(MbBaseVehicleApi):
    def __init__(self, mb_customer: MbCustomer, vin: str):
        super().__init__(
            mb_customer,
            vin,
            50,
            {
                MbPromResRepr.DECK_LID_LOCK_STATUS,
                MbPromResRepr.VEHICLE_LOCK_STATUS,
                MbPromResRepr.GAS_TANK_LOCK_STATUS,
                MbPromResRepr.VEHICLE_HEADING_POSITION,
            },
        )

    async def request(self) -> Response:
        return await self.mb_customer.get_async(
            f"https://api.mercedes-benz.com/vehicledata/v2/vehicles/{self.vin}/containers/vehiclelockstatus"
        )


class MbVehicleStatus(MbBaseVehicleApi):
    def __init__(self, mb_customer: MbCustomer, vin: str):
        super().__init__(
            mb_customer,
            vin,
            50,
            {
                MbPromResRepr.DECK_LID_STATUS,
                MbPromResRepr.DOOR_STATUS_FRONT_LEFT,
                MbPromResRepr.DOOR_STATUS_FRONT_RIGHT,
                MbPromResRepr.DOOR_STATUS_REAR_LEFT,
                MbPromResRepr.DOOR_STATUS_REAR_RIGHT,
                MbPromResRepr.INTERIOR_LIGHTS_FRONT,
                MbPromResRepr.INTERIOR_LIGHTS_REAR,
                MbPromResRepr.LIGHT_SWITCH_POSITION,
                MbPromResRepr.READING_LAMP_FRONT_LEFT,
                MbPromResRepr.READING_LAMP_FRONT_RIGHT,
                MbPromResRepr.ROOF_TOP_STATUS,
                MbPromResRepr.SUN_ROOF_STATUS,
                MbPromResRepr.WINDOW_STATUS_FRONT_LEFT,
                MbPromResRepr.WINDOW_STATUS_FRONT_RIGHT,
                MbPromResRepr.WINDOW_STATUS_REAR_LEFT,
                MbPromResRepr.WINDOW_STATUS_REAR_RIGHT,
            },
        )

    async def request(self) -> Response:
        return await self.mb_customer.get_async(
            f"https://api.mercedes-benz.com/vehicledata/v2/vehicles/{self.vin}/containers/vehiclestatus"
        )


class MbHybridVehicle:
    def __init__(self, mb_customer: MbCustomer, vin: str):
        self.mb_customer = mb_customer
        self.vin = vin

        self.apis = [
            MbElectricVehicleStatus(mb_customer, vin),
            MbFuelStatus(mb_customer, vin),
            MbOdometerStatus(mb_customer, vin),
            MbVehicleLockStatus(mb_customer, vin),
            MbVehicleStatus(mb_customer, vin),
        ]

        self.continuous_refresh_task: Optional[asyncio.Task] = None

    async def refresh(self):
        await asyncio.gather((api.refresh()) for api in self.apis)

    async def continuous_refresh(self):
        await asyncio.gather(*[(api.continuous_refresh()) for api in self.apis])

    def start(self):
        if (
            self.continuous_refresh_task
            and not self.continuous_refresh_task.cancelled()
        ):
            return
        if self.mb_customer.authorized:
            self.continuous_refresh_task = asyncio.create_task(
                self.continuous_refresh()
            )

    def stop(self):
        if (
            self.continuous_refresh_task
            and not self.continuous_refresh_task.cancelled()
        ):
            self.continuous_refresh_task.cancel()

    def running(self) -> bool:
        return self.continuous_refresh_task and not (
            self.continuous_refresh_task.done()
            or self.continuous_refresh_task.cancelled()
        )
