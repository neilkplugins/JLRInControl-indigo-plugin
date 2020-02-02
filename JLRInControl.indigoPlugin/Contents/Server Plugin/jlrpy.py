u""" Simple Python class to access the JLR Remote Car API
https://github.com/ardevd/jlrpy
"""

from __future__ import absolute_import
from urllib2 import Request, build_opener

import json
import datetime
import calendar
import uuid
import sys
import logging

logger = logging.getLogger(u'jply')
logger.setLevel(logging.INFO)

ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(logging.Formatter(u"%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(ch)
logger.propagate = False

IFAS_BASE_URL = u"https://ifas.prod-row.jlrmotor.com/ifas/jlr"
IFOP_BASE_ULR = u"https://ifop.prod-row.jlrmotor.com/ifop/jlr"
IF9_BASE_URL = u"https://if9.prod-row.jlrmotor.com/if9/jlr"


class Connection(object):
    u"""Connection to the JLR Remote Car API"""

    def __init__(self,
                 email=u'',
                 password=u'',
                 device_id=u'',
                 refresh_token=u''):
        u"""Init the connection object
        The email address and password associated with your Jaguar InControl account is required.
        A device Id can optionally be specified. If not one will be generated at runtime.
        A refresh token can be supplied for authentication instead of a password
        """
        self.email = email

        if device_id:
            self.device_id = device_id
        else:
            self.device_id = unicode(uuid.uuid4())

        if refresh_token:
            self.oauth = {
                u"grant_type": u"refresh_token",
                u"refresh_token": refresh_token}
        else:
            self.oauth = {
                u"grant_type": u"password",
                u"username": email,
                u"password": password}

        self.expiration = 0  # force credential refresh

        self.connect()

        self.vehicles = []
        try:
            for v in self.get_vehicles(self.head)[u'vehicles']:
                self.vehicles.append(Vehicle(v, self))
        except TypeError:
            logger.error(u"No vehicles associated with this account")

    def get(self, command, url, headers):
        u"""GET data from API"""
        return self.post(command, url, headers, None)

    def post(self, command, url, headers, data=None):
        u"""POST data to API"""
        now = calendar.timegm(datetime.datetime.now().timetuple())
        logger.debug(url)
        if now > self.expiration:
            # Auth expired, reconnect
            self.connect()
        return self.__open(u"%s/%s" % (url, command), headers=headers, data=data)

    def connect(self):
        logger.info(u"Connecting...")
        auth = self.__authenticate(data=self.oauth)
        self.__register_auth(auth)
        self.__set_header(auth[u'access_token'])
        logger.info(u"[+] authenticated")
        self.__register_device_and_log_in()

    def __register_device_and_log_in(self):
        self.__register_device(self.head)
        logger.info(u"1/2 device id registered")
        self.__login_user(self.head)
        logger.info(u"2/2 user logged in, user id retrieved")

    def __open(self, url, headers=None, data=None):
        req = Request(url, headers=headers)
        if data:
            req.data =str(json.dumps(data)).encode("utf8")

        opener = build_opener()
        resp = opener.open(req)
        charset = resp.info().get(u'charset', u'utf-8')
        resp_data = resp.read().decode(charset)
        if resp_data:
            return json.loads(resp_data)
        else:
            return None

    def __register_auth(self, auth):
        self.access_token = auth[u'access_token']
        now = calendar.timegm(datetime.datetime.now().timetuple())
        self.expiration = now + int(auth[u'expires_in'])
        self.auth_token = auth[u'authorization_token']
        self.refresh_token = auth[u'refresh_token']

    def __set_header(self, access_token):
        u"""Set HTTP header fields"""
        self.head = {
            u"Authorization": u"Bearer %s" % access_token,
            u"X-Device-Id": self.device_id,
            u"Content-Type": u"application/json"}

    def __authenticate(self, data=None):
        u"""Raw urlopen command to the auth url"""
        url = u"%s/tokens" % IFAS_BASE_URL
        auth_headers = {
            u"Authorization": u"Basic YXM6YXNwYXNz",
            u"Content-Type": u"application/json",
            u"X-Device-Id": self.device_id}

        return self.__open(url, auth_headers, data)

    def __register_device(self, headers=None):
        u"""Register the device Id"""
        url = u"%s/users/%s/clients" % (IFOP_BASE_ULR, self.email)
        data = {
            u"access_token": self.access_token,
            u"authorization_token": self.auth_token,
            u"expires_in": u"86400",
            u"deviceID": self.device_id
        }

        return self.__open(url, headers, data)

    def __login_user(self, headers=None):
        u"""Login the user"""
        url = u"%s/users?loginName=%s" % (IF9_BASE_URL, self.email)
        user_login_header = headers.copy()
        user_login_header[u"Accept"] = u"application/vnd.wirelesscar.ngtp.if9.User-v3+json"

        user_data = self.__open(url, user_login_header)
        self.user_id = user_data[u'userId']
        return user_data

    def refresh_tokens(self):
        u"""Refresh tokens."""
        self.oauth = {
            u"grant_type": u"refresh_token",
            u"refresh_token": self.refresh_token}

        auth = self.__authenticate(self.oauth)
        self.__register_auth(auth)
        self.__set_header(auth[u'access_token'])
        logger.info(u"[+] Tokens refreshed")
        self.__register_device_and_log_in()

    def get_vehicles(self, headers):
        u"""Get vehicles for user"""
        url = u"%s/users/%s/vehicles?primaryOnly=true" % (IF9_BASE_URL, self.user_id)
        return self.__open(url, headers)

    def get_user_info(self):
        u"""Get user information"""
        return self.get(self.user_id, u"%s/users" % IF9_BASE_URL, self.head)

    def update_user_info(self, user_info_data):
        u"""Update user information"""
        headers = self.head.copy()
        headers[u"Content-Type"] = u"application/vnd.wirelesscar.ngtp.if9.User-v3+json; charset=utf-8"
        return self.post(self.user_id, u"%s/users" % IF9_BASE_URL, headers, user_info_data)

    def reverse_geocode(self, lat, lon):
        u"""Get geocode information"""
        return self.get(u"en",
                        u"%s/geocode/reverse/{0:f}/{1:f}".format(lat, lon) % IF9_BASE_URL,
                        self.head)


class Vehicle(dict):
    u"""Vehicle class.
    You can request data or send commands to vehicle. Consult the JLR API documentation for details
    """

    def __init__(self, data, connection):
        u"""Initialize the vehicle class."""

        super(Vehicle, self).__init__(data)
        self.connection = connection
        self.vin = data[u'vin']

    def get_attributes(self):
        u"""Get vehicle attributes"""
        headers = self.connection.head.copy()
        headers[u"Accept"] = u"application/vnd.ngtp.org.VehicleAttributes-v3+json"
        result = self.get(u'attributes', headers)
        return result

    def get_status(self, key=None):
        u"""Get vehicle status"""
        headers = self.connection.head.copy()
        headers[u"Accept"] = u"application/vnd.ngtp.org.if9.healthstatus-v2+json"
        result = self.get(u'status', headers)

        if key:
            return dict((d[u'key'], d[u'value']) for d in result[u'vehicleStatus'])[key]

        return result

    def get_health_status(self):
        u"""Get vehicle health status"""
        headers = self.connection.head.copy()
        headers[u"Accept"] = u"application/vnd.wirelesscar.ngtp.if9.ServiceStatus-v4+json"
        headers[u"Content-Type"] = u"application/vnd.wirelesscar.ngtp.if9.StartServiceConfiguration-v3+json; charset=utf-8"

        vhs_data = self._authenticate_vhs()

        return self.post(u'healthstatus', headers, vhs_data)

    def get_departure_timers(self):
        u"""Get vehicle departure timers"""
        headers = self.connection.head.copy()
        headers[u"Accept"] = u"application/vnd.wirelesscar.ngtp.if9.DepartureTimerSettings-v1+json"
        return self.get(u"departuretimers", headers)

    def get_wakeup_time(self):
        u"""Get configured wakeup time for vehicle"""
        headers = self.connection.head.copy()
        headers[u"Accept"] = u"application/vnd.wirelesscar.ngtp.if9.VehicleWakeupTime-v2+json"
        return self.get(u"wakeuptime", headers)

    def get_subscription_packages(self):
        u"""Get vehicle status"""
        result = self.get(u'subscriptionpackages', self.connection.head)
        return result

    def get_trips(self, count=1000):
        u"""Get the last 1000 trips associated with vehicle"""
        headers = self.connection.head.copy()
        headers[u"Accept"] = u"application/vnd.ngtp.org.triplist-v2+json"
        return self.get(u'trips?count=%d' % count, headers)

    def get_trip(self, trip_id):
        u"""Get info on a specific trip"""
        return self.get(u'trips/%s/route?pageSize=1000&page=0' % trip_id, self.connection.head)

    def get_position(self):
        u"""Get current vehicle position"""
        return self.get(u'position', self.connection.head)

    def get_service_status(self, service_id):
        u"""Get service status"""
        headers = self.connection.head.copy()
        headers[u"Accept"] = u"application/vnd.wirelesscar.ngtp.if9.ServiceStatus-v4+json"
        return self.get(u'services/%s' % service_id, headers)

    def get_rcc_target_value(self):
        u"""Get Remote Climate Target Value"""
        headers = self.connection.head.copy()
        return self.get(u'settings/ClimateControlRccTargetTemp', headers)

    def set_attributes(self, nickname, registration_number):
        u"""Set vehicle nickname and registration number"""
        attributes_data = {u"nickname": nickname,
                           u"registrationNumber": registration_number}
        return self.post(u"attributes", self.connection.head, attributes_data)

    def lock(self, pin):
        u"""Lock vehicle. Requires personal PIN for authentication"""
        headers = self.connection.head.copy()
        headers[u"Content-Type"] = u"application/vnd.wirelesscar.ngtp.if9.StartServiceConfiguration-v2+json"
        rdl_data = self.authenticate_rdl(pin)

        return self.post(u"lock", headers, rdl_data)

    def unlock(self, pin):
        u"""Unlock vehicle. Requires personal PIN for authentication"""
        headers = self.connection.head.copy()
        headers[u"Content-Type"] = u"application/vnd.wirelesscar.ngtp.if9.StartServiceConfiguration-v2+json"
        rdu_data = self.authenticate_rdu(pin)

        return self.post(u"unlock", headers, rdu_data)

    def reset_alarm(self, pin):
        u"""Reset vehicle alarm"""
        headers = self.connection.head.copy()
        headers[u"Content-Type"] = u"application/vnd.wirelesscar.ngtp.if9.StartServiceConfiguration-v3+json; charset=utf-8"
        headers[u"Accept"] = u"application/vnd.wirelesscar.ngtp.if9.ServiceStatus-v4+json"
        aloff_data = self.authenticate_aloff(pin)

        return self.post(u"unlock", headers, aloff_data)

    def honk_blink(self):
        u"""Sound the horn and blink lights"""
        headers = self.connection.head.copy()
        headers[u"Accept"] = u"application/vnd.wirelesscar.ngtp.if9.ServiceStatus-v4+json"
        headers[u"Content-Type"] = u"application/vnd.wirelesscar.ngtp.if9.StartServiceConfiguration-v3+json; charset=utf-8"

        hblf_data = self.authenticate_hblf()
        return self.post(u"honkBlink", headers, hblf_data)

    def remote_engine_start(self, pin, target_value):
        u"""Start Remote Engine preconditioning"""
        headers = self.connection.head.copy()
        headers[u"Content-Type"] = u"application/vnd.wirelesscar.ngtp.if9.StartServiceConfiguration-v2+json"
        self.set_rcc_target_value(pin, target_value)
        reon_data = self.authenticate_reon(pin)

        return self.post(u"engineOn", headers, reon_data)

    def remote_engine_stop(self, pin):
        u"""Stop Remote Engine preconditioning"""
        headers = self.connection.head.copy()
        headers[u"Content-Type"] = u"application/vnd.wirelesscar.ngtp.if9.StartServiceConfiguration-v2+json"
        reoff_data = self.authenticate_reoff(pin)

        return self.post(u"engineOff", headers, reoff_data)

    def set_rcc_target_value(self, pin, target_value):
        u"""Set Remote Climate Target Value (value between 31-57, 31 is LO 57 is HOT)"""
        headers = self.connection.head.copy()
        self.enable_provisioning_mode(pin)
        service_parameters = {u"key": u"ClimateControlRccTargetTemp",
                               u"value": u"%s" % unicode(target_value),
                               u"applied": 1}
        self.post(u"settings", headers, service_parameters)

    def preconditioning_start(self, target_temp):
        u"""Start pre-conditioning for specified temperature (celsius)"""
        service_parameters = [{u"key": u"PRECONDITIONING",
                               u"value": u"START"},
                              {u"key": u"TARGET_TEMPERATURE_CELSIUS",
                               u"value": u"%s" % target_temp}]

        return self._preconditioning_control(service_parameters)

    def preconditioning_stop(self):
        u"""Stop climate preconditioning"""
        service_parameters = [{u"key": u"PRECONDITIONING",
                               u"value": u"STOP"}]
        return self._preconditioning_control(service_parameters)

    def climate_prioritize(self, priority):
        u"""Optimize climate controls for comfort or range"""
        service_parameters = [{u"key": u"PRIORITY_SETTING",
                               u"value": u"%s" % priority}]
        return self._preconditioning_control(service_parameters)

    def _preconditioning_control(self, service_parameters):
        u"""Control the climate preconditioning"""
        headers = self.connection.head.copy()
        headers[u"Accept"] = u"application/vnd.wirelesscar.ngtp.if9.ServiceStatus-v5+json"
        headers[u"Content-Type"] = u"application/vnd.wirelesscar.ngtp.if9.PhevService-v1+json; charset=utf"

        ecc_data = self.authenticate_ecc()
        ecc_data[u'serviceParameters'] = service_parameters

        return self.post(u"preconditioning", headers, ecc_data)

    def charging_stop(self):
        u"""Stop charging"""
        service_parameters = [{u"key": u"CHARGE_NOW_SETTING",
                               u"value": u"FORCE_OFF"}]

        return self._charging_profile_control(u"serviceParameters", service_parameters)

    def charging_start(self):
        u"""Start charging"""
        service_parameters = [{u"key": u"CHARGE_NOW_SETTING",
                               u"value": u"FORCE_ON"}]

        return self._charging_profile_control(u"serviceParameters", service_parameters)

    def set_max_soc(self, max_charge_level):
        u"""Set max state of charge in percentage"""
        service_parameters = [{u"key": u"SET_PERMANENT_MAX_SOC",
                               u"value": max_charge_level}]

        return self._charging_profile_control(u"serviceParameters", service_parameters)

    def set_one_off_max_soc(self, max_charge_level):
        u"""Set one off max state of charge in percentage"""
        service_parameters = [{u"key": u"SET_ONE_OFF_MAX_SOC",
                               u"value": max_charge_level}]

        return self._charging_profile_control(u"serviceParameters", service_parameters)

    def add_departure_timer(self, index, year, month, day, hour, minute):
        u"""Add a single departure timer with the specified index"""
        departure_timer_setting = {u"timers": [
            {u"departureTime": {u"hour": hour, u"minute": minute},
             u"timerIndex": index, u"timerTarget":
                 {u"singleDay": {u"day": day, u"month": month, u"year": year}},
             u"timerType": {u"key": u"BOTHCHARGEANDPRECONDITION", u"value": True}}]}

        return self._charging_profile_control(u"departureTimerSetting", departure_timer_setting)

    def add_repeated_departure_timer(self, index, schedule, hour, minute):
        u"""Add repeated departure timer."""
        departure_timer_setting = {u"timers": [
            {u"departureTime": {u"hour": hour, u"minute": minute},
             u"timerIndex": index, u"timerTarget":
                 {u"repeatSchedule": schedule},
             u"timerType": {u"key": u"BOTHCHARGEANDPRECONDITION", u"value": True}}]}

        return self._charging_profile_control(u"departureTimerSetting", departure_timer_setting)

    def delete_departure_timer(self, index):
        u"""Delete a single departure timer associated with the specified index"""
        departure_timer_setting = {u"timers": [{u"timerIndex": index}]}

        return self._charging_profile_control(u"departureTimerSetting", departure_timer_setting)

    def add_charging_period(self, index, schedule, hour_from, minute_from, hour_to, minute_to):
        u"""Add charging period"""
        tariff_settings = {u"tariffs": [
            {u"tariffIndex": index, u"tariffDefinition": {u"enabled": True,
                                                        u"repeatSchedule": schedule,
                                                        u"tariffZone": [
                                                            {u"zoneName": u"TARIFF_ZONE_A",
                                                             u"bandType": u"PEAK",
                                                             u"endTime": {
                                                                 u"hour": hour_from,
                                                                 u"minute": minute_from}},
                                                            {u"zoneName": u"TARIFF_ZONE_B",
                                                             u"bandType": u"OFFPEAK",
                                                             u"endTime": {u"hour": hour_to,
                                                                         u"minute": minute_to}},
                                                            {u"zoneName": u"TARIFF_ZONE_C",
                                                             u"bandType": u"PEAK",
                                                             u"endTime": {u"hour": 0,
                                                                         u"minute": 0}}]}}]}

        return self._charging_profile_control(u"tariffSettings", tariff_settings)

    def _charging_profile_control(self, service_parameter_key, service_parameters):
        u"""Charging profile API"""
        headers = self.connection.head.copy()
        headers[u"Accept"] = u"application/vnd.wirelesscar.ngtp.if9.ServiceStatus-v5+json"
        headers[u"Content-Type"] = u"application/vnd.wirelesscar.ngtp.if9.PhevService-v1+json; charset=utf-8"

        cp_data = self.authenticate_cp()
        cp_data[service_parameter_key] = service_parameters

        return self.post(u"chargeProfile", headers, cp_data)

    def set_wakeup_time(self, wakeup_time):
        u"""Set the wakeup time for the specified time (epoch milliseconds)"""
        swu_data = self.authenticate_swu()
        swu_data[u"serviceCommand"] = u"START"
        swu_data[u"startTime"] = wakeup_time
        return self._swu(swu_data)

    def delete_wakeup_time(self):
        u"""Stop the wakeup time"""
        swu_data = self.authenticate_swu()
        swu_data[u"serviceCommand"] = u"END"
        return self._swu(swu_data)

    def _swu(self, swu_data):
        u"""Set the wakeup time for the specified time (epoch milliseconds)"""
        headers = self.connection.head.copy()
        headers[u"Accept"] = u"application/vnd.wirelesscar.ngtp.if9.ServiceStatus-v3+json"
        headers[u"Content-Type"] = u"application/vnd.wirelesscar.ngtp.if9.StartServiceConfiguration-v3+json; charset=utf-8"
        return self.post(u"swu", headers, swu_data)

    def enable_provisioning_mode(self, pin):
        u"""Enable provisioning mode """
        self._prov_command(pin, None, u"provisioning")

    def enable_service_mode(self, pin, expiration_time):
        u"""Enable service mode. Will disable at the specified time (epoch millis)"""
        return self._prov_command(pin, expiration_time, u"protectionStrategy_serviceMode")

    def enable_transport_mode(self, pin, expiration_time):
        u"""Enable transport mode. Will be disabled at the specified time (epoch millis)"""
        return self._prov_command(pin, expiration_time, u"protectionStrategy_transportMode")

    def enable_privacy_mode(self, pin):
        u"""Enable privacy mode. Will disable journey logging"""
        return self._prov_command(pin, None, u"privacySwitch_on")

    def disable_privacy_mode(self, pin):
        u"""Disable privacy mode. Will enable journey logging"""
        return self._prov_command(pin, None, u"privacySwitch_off")

    def _prov_command(self, pin, expiration_time, mode):
        u"""Send prov endpoint commands. Used for service/transport/privacy mode"""
        headers = self.connection.head.copy()
        headers[u"Accept"] = u"application/vnd.wirelesscar.ngtp.if9.ServiceStatus-v4+json"
        headers[u"Content-Type"] = u"application/vnd.wirelesscar.ngtp.if9.StartServiceConfiguration-v3+json; charset=utf-8"

        prov_data = self.authenticate_prov(pin)

        prov_data[u"serviceCommand"] = mode
        prov_data[u"startTime"] = None
        prov_data[u"endTime"] = expiration_time

        return self.post(u"prov", headers, prov_data)

    def _authenticate_vhs(self):
        u"""Authenticate to vhs and get token"""
        return self._authenticate_empty_pin_protected_service(u"VHS")

    def _authenticate_empty_pin_protected_service(self, service_name):
        data = {
            u"serviceName": service_name,
            u"pin": u""}
        headers = self.connection.head.copy()
        headers[u"Content-Type"] = u"application/vnd.wirelesscar.ngtp.if9.AuthenticateRequest-v2+json; charset=utf-8"

        return self.post(u"users/%s/authenticate" % self.connection.user_id, headers, data)

    def authenticate_hblf(self):
        u"""Authenticate to hblf"""
        return self._authenticate_vin_protected_service(u"HBLF")

    def authenticate_ecc(self):
        u"""Authenticate to ecc"""
        return self._authenticate_vin_protected_service(u"ECC")

    def authenticate_cp(self):
        u"""Authenticate to cp"""
        return self._authenticate_vin_protected_service(u"CP")

    def authenticate_swu(self):
        u"""Authenticate to swu"""
        return self._authenticate_empty_pin_protected_service(u"SWU")

    def _authenticate_vin_protected_service(self, service_name):
        u"""Authenticate to specified service and return associated token"""
        data = {
            u"serviceName": u"%s" % service_name,
            u"pin": u"%s" % self.vin[-4:]}
        headers = self.connection.head.copy()
        headers[u"Content-Type"] = u"application/vnd.wirelesscar.ngtp.if9.AuthenticateRequest-v2+json; charset=utf-8"

        return self.post(u"users/%s/authenticate" % self.connection.user_id, headers, data)

    def authenticate_rdl(self, pin):
        u"""Authenticate to rdl"""
        return self._authenticate_pin_protected_service(pin, u"RDL")

    def authenticate_rdu(self, pin):
        u"""Authenticate to rdu"""
        return self._authenticate_pin_protected_service(pin, u"RDU")

    def authenticate_aloff(self, pin):
        u"""Authenticate to aloff"""
        return self._authenticate_pin_protected_service(pin, u"ALOFF")

    def authenticate_reon(self, pin):
        u"""Authenticate to reon"""
        return self._authenticate_pin_protected_service(pin, u"REON")

    def authenticate_reoff(self, pin):
        u"""Authenticate to reoff"""
        return self._authenticate_pin_protected_service(pin, u"REOFF")

    def authenticate_prov(self, pin):
        u"""Authenticate to PROV service"""
        return self._authenticate_pin_protected_service(pin, u"PROV")

    def _authenticate_pin_protected_service(self, pin, service_name):
        u"""Authenticate to specified service with the provided PIN"""
        data = {
            u"serviceName": u"%s" % service_name,
            u"pin": u"%s" % pin}
        headers = self.connection.head.copy()
        headers[u"Content-Type"] = u"application/vnd.wirelesscar.ngtp.if9.AuthenticateRequest-v2+json; charset=utf-8"

        return self.post(u"users/%s/authenticate" % self.connection.user_id, headers, data)

    def post(self, command, headers, data):
        u"""Utility command to post data to VHS"""
        return self.connection.post(command, u'%s/vehicles/%s' % (IF9_BASE_URL, self.vin),
                                    headers, data)

    def get(self, command, headers):
        u"""Utility command to get vehicle data from API"""
        return self.connection.get(command, u'%s/vehicles/%s' % (IF9_BASE_URL, self.vin), headers)
