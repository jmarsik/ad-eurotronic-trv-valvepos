import appdaemon.plugins.hass.hassapi as hass
import os
import re
import datetime

# EUROTRONIC Z-Wave TRV helper AppDaemon application
# - allows access to "valve position (%)" value from Z-Wave TRVs (like SPIRIT) in Home Assistant
# - normally Home Assistant doesn't expose this value (at least in version 0.103)
class EurotronicTRVValvePos(hass.Hass):

    def initialize(self):
        # start time of "run every" task is set to 15 seconds in the future to avoid "start cannot be in the past" errors from AppDaemon
        self.run_every(self.read_valvepos_from_log, datetime.datetime.now() + datetime.timedelta(0, 15), int(self.args.get("refresh_seconds", str(5 * 60))))

    def read_valvepos_from_log(self, kwargs):
        ozw_log_path = self.args.get("ozw_log_path", "/config/OZW_Log.txt")
        self.log("Using OZW log file " + ozw_log_path)

        with open(ozw_log_path, "r") as f:
            # read OZW log file
            lines = f.read().splitlines()

            climates = self.get_state("climate")

            zwaves = self.get_state("zwave")
            for entity, v in zwaves.items():
                # ignore entities without product_name attribute
                if "product_name" not in v["attributes"]:
                    continue;

                # iterate over zwave domain entities, look for specific "product_name" attribute value
                # that value indicates that the entity is Z-Wave device entity for EUROTRONIC TRV
                if (v["attributes"]["product_name"] == self.args.get("look_for_productname", "EUR_SPIRITZ Wall Radiator Thermostat")):
                    node_id = v["attributes"]["node_id"]
                    self.log("Processing Z-Wave node ID " + str(node_id), level = "DEBUG")

                    # look for climate entity associated with this Z-Wave device entity, for friendly_name scraping
                    climate = next((i2 for i2 in climates.values() if i2["attributes"].get("node_id") == node_id), None)
                    if climate:
                        friendly_name = climate["attributes"].get("friendly_name")
                        if friendly_name:
                            self.log("Found corresponding climate entity [" + climate["entity_id"] + "] and using it's friendly name [" + friendly_name + "]", level = "DEBUG")
                            friendly_name += " valve position"
                        else:
                            friendly_name = "Z-Wave Node " + str(node_id) + " EUROTRONIC valve position"

                    lookfor = f'Node{node_id:03}, Received SwitchMultiLevel report'
                    self.log("Looking for [" + lookfor + "] in OZW log file")

                    # reverse-search log file for a line with  SwitchMultiLevel report for detected node ID
                    line = next((i for i in reversed(lines) if lookfor in i), None)
                    if line:
                        self.log("Found line [" + line + "]")
                        # parse datetime and level value
                        match = re.search(r"(^[0-9-:. ]+) .*level=([0-9]+)$", line)
                        if match:
                            self.log("Extracted level [" + match.group(2) + "] and datetime [" + match.group(1) + "]")
                            # create HA entity
                            self.set_state("sensor.zwave_node" + str(node_id) + "_eurotronic_valve_position",
                                state = match.group(2),
                                attributes = {
                                    "source": self.name,
                                    "node_id": node_id,
                                    "unit_of_measurement": "%",
                                    "last_extracted": match.group(1),
                                    "friendly_name": friendly_name
                                })
