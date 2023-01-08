#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Copyright (c) 2020 neilk
#
# Based on the sample dimmer plugin and various vehicle plugins for Indigo
# Uses the jlrpy Library from https://github.com/ardevd/jlrpy

################################################################################
# Imports
################################################################################
import indigo
import requests
import json
import time as t
import jlrpy

################################################################################
# Globals
################################################################################
kpaInPSI = 0.145038
kpaInBar = 0.01


####################################
# Validate Email Input - Simple checks form, not if it exists ToDo doesn't work
####################################

# def invalid_email(email_address):
# 	a=0
# 	y=len(email_address)
# 	dot=email_address.find(".")
# 	at=email_address.find("@")
# 	for i in range (0,at):
# 		if((email_address[i]>='a' and email_address[i]<='z') or (email_address[i]>='A' and email_address[i]<='Z')):
# 			a=a+1
# 		if(a>0 and at>0 and (dot-at)>0 and (dot+1)<y):
# 			return (False)
# 	else:
# 		return (False)


################################################################################
class Plugin(indigo.PluginBase):
    ########################################
    # Class properties
    ########################################

    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.debug = pluginPrefs.get("showDebugInfo", False)
        self.deviceList = []

    ########################################
    def deviceStartComm(self, device):
        self.debugLog("Starting device: " + device.name)
        self.debugLog(str(device.id) + " " + device.name)
        device.stateListOrDisplayStateIdChanged()
        if device.id not in self.deviceList:
            self.update(device)
            self.deviceList.append(device.id)

    ########################################
    def deviceStopComm(self, device):
        self.debugLog("Stopping device: " + device.name)
        if device.id in self.deviceList:
            self.deviceList.remove(device.id)

    ########################################
    def runConcurrentThread(self):
        self.debugLog("Starting concurrent thread")
        try:
            pollingFreq = int(self.pluginPrefs['pollingFrequency'])
        except:
            pollingFreq = 60
        try:
            while True:
                # we sleep (by a user defined amount, default 60s) first because when the plugin starts, each device
                # is updated as they are started.
                self.sleep(1 * pollingFreq)
                # now we cycle through each vehicle device
                for deviceId in self.deviceList:
                    # call the update method with the device instance
                    self.update(indigo.devices[deviceId])
        except self.StopThread:
            pass

    ########################################
    def update(self, device):
        try:
            c = jlrpy.Connection(self.pluginPrefs['InControlEmail'], self.pluginPrefs['InControlPassword'])
            # The Car ID from the device defintion maps to the relevant car if multiple cars on one account
            # Adjust for index starting at 0
        except:
            indigo.server.log("Failed to Contact JLR In Control Servers")
            return ()
        vehicle_num = int(device.pluginProps['CarID']) - 1
        v = c.vehicles[vehicle_num]
        device.updateStateOnServer('deviceIsOnline', value=True, uiValue="Starting")

        user_info = c.get_user_info()
        status = v.get_status()['vehicleStatus']['coreStatus']
        self.debugLog(status)
        attributes = v.get_attributes()
        location = v.get_position()
        # reverse geocode call appears to be broken in jlpr
        # revgeocode = c.reverse_geocode(location['position']['latitude'],location['position']['longitude'] )
        self.debugLog("Updating device: " + device.name)
        # states = []
        # states.append({ 'key' : "address", 'value' : v['vin']})
        device_states = []
        # Update Vehicle Status
        #for d in v.get_status()['vehicleStatus']:
        for d in status:
            if d['key'] == 'EV_STATE_OF_CHARGE':
                 device_states.append({'key': d['key'], 'value': d['value'], 'uiValue': (d['value'] + '%')})
            elif d['key'] == "EV_CHARGING_RATE_SOC_PER_HOUR":
                 device_states.append({'key': d['key'], 'value': d['value'], 'uiValue': (d['value'] + '%')})
            elif d['key'] == "EV_MINUTES_TO_FULLY_CHARGED":
                 hours = '{:02d}:{:02d}m'.format(*divmod(int(d['value']), 60))
                 device_states.append({'key': d['key'], 'value': d['value'], 'uiValue': hours})
            elif d['key'] == "EV_CHARGING_STATUS":
                 if d['value'] == "No Message":
                     uicharge = "Not Connected"
                 else:
                     uicharge = d['value']
                     device_states.append({'key': d['key'], 'value': d['value'], 'uiValue': uicharge})
            elif d['key'] == "THEFT_ALARM_STATUS":
                 if d['value'] == "ALARM_ARMED":
                     uialarm = "Armed"
                 elif d['value'] == "ALARM_OFF":
                     uialarm = "Not Armed"
                 else:
                     uialarm = d['value']
                 device_states.append({'key': d['key'], 'value': d['value'], 'uiValue': uialarm})
            elif d['key'] == "EV_RANGE_VSC_REVISED_HV_BATT_ENERGYx100":
                 device_states.append({'key': d['key'], 'value': d['value'], 'uiValue': (d['value'] + ' kWh')})
            elif "TYRE_PRESSURE" in d['key']:
                 if self.pluginPrefs['pressureunit'] == "Bar":
                     convertedpressure = round(float(d['value']) * kpaInBar, 1)
                     uipressure = str(convertedpressure) + " Bar"
                 else:
                     convertedpressure = round(float(d['value']) * kpaInPSI, 1)
                     uipressure = str(convertedpressure) + " Psi"
                 device_states.append({'key': d['key'], 'value': d['value'], 'uiValue': uipressure})
            elif d['key'] == "DOOR_IS_ALL_DOORS_LOCKED":
                 if d['value']:
                     uilock = "Locked"
                 else:
                     uilock = "Unlocked"
                 device_states.append({'key': d['key'], 'value': d['value'], 'uiValue': uilock})
            else:
                 device_states.append({'key': d['key'], 'value': d['value']})
        device_states.append({'key': 'modelYear', 'value': attributes['modelYear']})
        device_states.append({'key': 'vehicleBrand', 'value': attributes['vehicleBrand']})
        device_states.append({'key': 'fuelType', 'value': attributes['fuelType']})
        device_states.append({'key': 'vehicleType', 'value': attributes['vehicleType']})
        device_states.append({'key': 'nickname', 'value': attributes['nickname']})
        device_states.append({'key': 'exteriorColorName', 'value': attributes['exteriorColorName']})
        device_states.append({'key': 'registrationNumber', 'value': attributes['registrationNumber']})
        device_states.append({'key': 'bodyType', 'value': attributes['bodyType']})
        device_states.append({'key': 'longitude', 'value': location['position']['longitude']})
        device_states.append({'key': 'latitude', 'value': location['position']['latitude']})
        device_states.append({'key': 'speed', 'value': location['position']['speed']})
        device_states.append({'key': 'heading', 'value': location['position']['heading']})
        # device_states.append({ 'key': 'geoaddress' , 'value' : revgeocode['formattedAddress'] })
        # self.debugLog(device_states)
        self.debugLog("States Updated - Generating Map")
        baseurl = "https://www.mapquestapi.com/staticmap/v5/map?locations="
        locationsection = str(location['position']['latitude']) + "," + str(location['position']['longitude'])
        sizeandapikey = "&size=@2x&key=" + self.pluginPrefs['mapAPIkey']
        mapurl = baseurl + locationsection + sizeandapikey
        # url = "https://www.mapquestapi.com/staticmap/v5/map?locations="+str(location['position']['latitude'])+","+str(location['position']['longitude'])+"&size=@2x&key="+self.pluginPrefs['mapAPIkey']
        imagepath = "{}/IndigoWebServer/images/controls/static/carlocation{}.jpg".format(
            indigo.server.getInstallFolderPath(), str(vehicle_num + 1))
        self.debugLog(imagepath)
        if self.pluginPrefs['useMapAPI']:
            try:
                r = requests.get(mapurl, timeout=0.5)
                if r.status_code == 200:
                    with open(imagepath, 'wb') as f:
                        f.write(r.content)
                        self.debugLog("Writing Car Location Image")
            except:
                indigo.server.log("Error writing Car Location Map Image")
        update_time = t.strftime("%m/%d/%Y at %H:%M")
        device_states.append({'key': 'deviceLastUpdated', 'value': update_time})
        # device.updateStateOnServer('deviceLastUpdated', value=update_time)
        # device.updateStateOnServer('deviceTimestamp', value=t.time())
        device_states.append({'key': 'deviceTimestamp', 'value': t.time()})
        device_states.append({'key': 'deviceIsOnline', 'value': True, 'uiValue': "Online"})
        device.updateStatesOnServer(device_states)
        # device.updateStateOnServer('deviceIsOnline', value=True, uiValue="Online")
        self.debugLog("Done Updating States and Map")
        indigo.server.log("Upating States & Map Complete")
        return ()

    ########################################
    # UI Validate, Device Config
    ########################################
    def validateDeviceConfigUi(self, valuesDict, typeId, device):
        c = jlrpy.Connection(self.pluginPrefs['InControlEmail'], self.pluginPrefs['InControlPassword'])
        # The Car ID from the device defintion maps to the relevant car if multiple cars on one account
        # Adjust for index starting at 0
        self.debugLog(valuesDict)
        vehicle_num = int(valuesDict['CarID']) - 1
        v = c.vehicles[vehicle_num]
        adjustedtemp = valuesDict['climateTemp'] + "0"
        valuesDict['address'] = v['vin']
        valuesDict['adjustedclimateTemp'] = adjustedtemp
        self.debugLog(valuesDict)
        return (True, valuesDict)

    ########################################
    # UI Validate, Plugin Preferences
    ########################################
    def validatePrefsConfigUi(self, valuesDict):
        # if invalid_email(valuesDict['InControlEmail']):
        #     		self.errorLog("Invalid email address for JLR InControl")
        #     		errorsDict = indigo.Dict()
        #     		errorsDict['InControlEmail'] = "Invalid email address for JLR InControl"
        #     		return (False, valuesDict, errorsDict)
        if not (valuesDict['InControlPassword']):
            self.errorLog("Password Cannot Be Empty")
            errorsDict = indigo.Dict()
            errorsDict['InControlPassword'] = "Password Cannot Be Empty"
            return (False, valuesDict, errorsDict)
        if not (valuesDict['InControlPIN']):
            self.errorLog("PIN Cannot Be Empty")
            errorsDict = indigo.Dict()
            errorsDict['InControlPIN'] = "PIN Cannot Be Empty"
            return (False, valuesDict, errorsDict)
        try:
            timeoutint = float(valuesDict['requeststimeout'])
        except:
            self.errorLog("Invalid entry for  JLR API Timeout - must be a number")
            errorsDict = indigo.Dict()
            errorsDict['requeststimeout'] = "Invalid entry for JLR API Timeout - must be a number"
            return (False, valuesDict, errorsDict)
        try:
            pollingfreq = int(valuesDict['pollingFrequency'])
        except:
            self.errorLog("Invalid entry for JLR Polling Frequency - must be a whole number greater than 0")
            errorsDict = indigo.Dict()
            errorsDict[
                'pollingFrequency'] = "Invalid entry for JLR Polling Frequency - must be a whole number greater than 0"
            return (False, valuesDict, errorsDict)
        if int(valuesDict['pollingFrequency']) == 0:
            self.errorLog("Invalid entry for JLR Polling Frequency - must be greater than 0")
            errorsDict = indigo.Dict()
            errorsDict[
                'pollingFrequency'] = "Invalid entry for JLR Polling Frequency - must be a whole number greater than 0"
            return (False, valuesDict, errorsDict)
        if int(valuesDict['requeststimeout']) == 0:
            self.errorLog("Invalid entry for JLR Requests Timeout - must be greater than 0")
            errorsDict = indigo.Dict()
            errorsDict['requeststimeout'] = "Invalid entry for JLR Requests Timeout - must be greater than 0"
            return (False, valuesDict, errorsDict)
        try:
            connection = jlrpy.Connection(valuesDict['InControlEmail'], valuesDict['InControlPassword'])
        except:
            self.errorLog("Error connecting to JLR Servers - Check Email and Password")
            errorsDict = indigo.Dict()
            errorsDict['InControlAccountEmail'] = "Invalid email address for JLR InControl"
            errorsDict['InControlPassword'] = "or password not correct"
            return (False, valuesDict, errorsDict)
        # error is HTTPError: HTTP Error 403: Forbidden
        # Otherwise we are good, log details for debugging
        self.debugLog("Successfully Connected to JLR Servers")
        self.debugLog(
            str(len(connection.vehicles)) + " Vehicle Available for account " + valuesDict['InControlAccountEmail'])
        self.debugLog(connection.vehicles)
        return (True, valuesDict)

    ########################################
    # UI Validate, Actions
    ########################################
    def validateActionConfigUi(self, valuesDict, typeId, deviceId):
        self.debugLog(valuesDict)
        # Validate Intensity
        if 'effectintensity' in valuesDict:
            try:
                effectintensity = int(valuesDict['effectintensity'])
            except:
                self.errorLog("Invalid entry for Effect Intensity - must be a whole number between 0 and 255")
                errorsDict = indigo.Dict()
                errorsDict[
                    'effectintensity'] = "Invalid entry for Effect Intensity - must be a whole number between 0 and 255"
                return (False, valuesDict, errorsDict)
            self.debugLog(int(valuesDict['effectintensity']))
            if not (int(valuesDict['effectintensity']) in xrange(0, 256)):
                # if 0 <= int(valuesDict['effectintensity']) >= 256:
                self.errorLog("Invalid entry for Effect Intensity - must be a whole number between 0 and 255")
                errorsDict = indigo.Dict()
                errorsDict[
                    'effectintensity'] = "Invalid entry for Effect Intensity - must be a whole number between 0 and 255"
                return (False, valuesDict, errorsDict)

        # Otherwise we are all good
        return (True, valuesDict)

    ########################################
    # Menu Methods
    ########################################
    def toggleDebugging(self):
        if self.debug:
            indigo.server.log("Turning off debug logging")
            self.pluginPrefs["showDebugInfo"] = False
        else:
            indigo.server.log("Turning on debug logging")
            self.pluginPrefs["showDebugInfo"] = True
        self.debug = not self.debug

    ########################################
    # Method to populate vehicle list for device configuration menu
    ########################################    

    def genVehicleList(self, filter, valuesDict, typeId, devID):
        device = indigo.devices[devID]
        try:
            connection = jlrpy.Connection(self.pluginPrefs['InControlEmail'], self.pluginPrefs['InControlPassword'])
        except:
            self.errorLog("Error connecting to JLR Servers - Check Email and Password")
        self.debugLog("Successfully Connected to JLR Servers")
        # error is HTTPError: HTTP Error 403: Forbidden
        # Retrieve the list of vehicles from JLRpy and write out the Vehicle Identification numbers to the event log so they can match to the right car
        # Only necessary if multiple cars added to the same account
        vehiclelist = connection.vehicles
        vin = []
        for item in vehiclelist:
            vin.append(item['vin'])
        # Dump to event log the number of vehicles associated with the account
        indigo.server.log(
            str(len(vehiclelist)) + " Vehicle(s) Available for InControl account " + self.pluginPrefs['InControlEmail'])
        self.debugLog(vehiclelist)
        self.debugLog(vin)
        vid = []
        for index, item in enumerate(vehiclelist):
            self.debugLog(index)
            vid.append(str(index + 1))
            # Output to event log the numbers for the menu mapped to the VIN number by account
            indigo.server.log("For menu number " + str(index + 1) + " VIN is " + vehiclelist[index]['vin'])
        indigo.server.log("VIN Can be found on the assistance tab of the InControl App")
        return vid

    def honkAndBlink(self, pluginAction, dev):
        self.debugLog(dev)
        c = jlrpy.Connection(self.pluginPrefs['InControlEmail'], self.pluginPrefs['InControlPassword'])
        # The Car ID from the device defintion maps to the relevant car if multiple cars on one account
        # Adjust for index starting at 0
        vehicle_num = int(dev.pluginProps['CarID']) - 1
        v = c.vehicles[vehicle_num]
        v.honk_blink()
        self.debugLog("Honked and Blinked")
        return ()

    def startCharge(self, pluginAction, dev):
        self.debugLog(dev)
        c = jlrpy.Connection(self.pluginPrefs['InControlEmail'], self.pluginPrefs['InControlPassword'])
        # The Car ID from the device defintion maps to the relevant car if multiple cars on one account
        # Adjust for index starting at 0
        vehicle_num = int(dev.pluginProps['CarID']) - 1
        v = c.vehicles[vehicle_num]
        v.charging_start()
        self.debugLog("Charge Started")
        return ()

    def stopCharge(self, pluginAction, dev):
        self.debugLog(dev)
        c = jlrpy.Connection(self.pluginPrefs['InControlEmail'], self.pluginPrefs['InControlPassword'])
        # The Car ID from the device defintion maps to the relevant car if multiple cars on one account
        # Adjust for index starting at 0
        vehicle_num = int(dev.pluginProps['CarID']) - 1
        v = c.vehicles[vehicle_num]
        v.charging_start()
        self.debugLog("Charge Stopped")
        return ()

    def stopClimate(self, pluginAction, dev):
        self.debugLog(dev)
        c = jlrpy.Connection(self.pluginPrefs['InControlEmail'], self.pluginPrefs['InControlPassword'])
        # The Car ID from the device defintion maps to the relevant car if multiple cars on one account
        # Adjust for index starting at 0
        vehicle_num = int(dev.pluginProps['CarID']) - 1
        v = c.vehicles[vehicle_num]
        v.preconditioning_stop()
        self.debugLog("Climate Stopped")
        return ()

    def startClimate(self, pluginAction, dev):
        self.debugLog(dev)
        c = jlrpy.Connection(self.pluginPrefs['InControlEmail'], self.pluginPrefs['InControlPassword'])
        # The Car ID from the device defintion maps to the relevant car if multiple cars on one account
        # Adjust for index starting at 0
        vehicle_num = int(dev.pluginProps['CarID']) - 1
        v = c.vehicles[vehicle_num]
        v.preconditioning_start(pluginAction.props.get('climatetemp'))
        self.debugLog("Climate Started at " + pluginAction.props.get('climatetemp'))
        return ()

    ########################################
    # Relay / Dimmer Action callback
    ######################

    def actionControlDevice(self, action, dev):
        ###### TURN ON Timed Climate ######
        if action.deviceAction == indigo.kDeviceAction.TurnOn:
            jsondata = json.dumps({"on": True})
            try:
                c = jlrpy.Connection(self.pluginPrefs['InControlEmail'], self.pluginPrefs['InControlPassword'])
                # The Car ID from the device defintion maps to the relevant car if multiple cars on one account
                # Adjust for index starting at 0
                vehicle_num = int(dev.pluginProps['CarID']) - 1
                v = c.vehicles[vehicle_num]
                v.preconditioning_start(dev.pluginProps['adjustedclimateTemp'])
                self.debugLog("Climate Started at " + dev.pluginProps['adjustedclimateTemp'])
                sendSuccess = True
            except:
                sendSuccess = False

            if sendSuccess:
                # If success then log that the command was successfully sent.
                indigo.server.log(u"Turned Timed Climate \"%s\" %s" % (dev.name, "on"))

                # And then tell the Indigo Server to update the state.
                dev.updateStateOnServer("onOffState", True)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                indigo.server.log(u"Turning Timed Climate \"%s\" to %s failed" % (dev.name, "on"), isError=True)

        ###### TURN OFF Timed Climate ######
        elif action.deviceAction == indigo.kDeviceAction.TurnOff:
            # Turn WLED off
            jsondata = json.dumps({"on": False})
            try:
                c = jlrpy.Connection(self.pluginPrefs['InControlEmail'], self.pluginPrefs['InControlPassword'])
                # The Car ID from the device defintion maps to the relevant car if multiple cars on one account
                # Adjust for index starting at 0
                vehicle_num = int(dev.pluginProps['CarID']) - 1
                v = c.vehicles[vehicle_num]
                v.preconditioning_stop()
                self.debugLog("Climate Stopped")
                sendSuccess = True
            except:
                sendSuccess = False

            if sendSuccess:
                # If success then log that the command was successfully sent.
                indigo.server.log(u"sent \"%s\" %s" % (dev.name, "off"))

                # And then tell the Indigo Server to update the state:
                dev.updateStateOnServer("onOffState", False)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "off"), isError=True)


        ###### TOGGLE ######
        elif action.deviceAction == indigo.kDeviceAction.Toggle:
            # Toggle the WLED
            self.debugLog("Device for Timed Climate does not support toggle")
