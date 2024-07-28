from dataclasses import dataclass

debugHTML = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="color-scheme" content="light dark" />
    <title>SEMP Overview</title>

    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2.0.6/css/pico.classless.min.css" integrity="sha256-x6eJE6DWO+0qwgv4JXN3jXY3/GIzHSlVoH0jcdsLHEQ=" crossorigin="anonymous">
  <style>
        [role="tabs"] {
        display: flex;
        }

        [role="tabs"] section {
        display: flex;
        flex-wrap: wrap;
        width: 100%;
        }

        [role="tabs"] figure {
        flex-grow: 1;
        width: 100%;
        height: 100%;
        display: none;
        }

        [role="tabs"] [type="radio"]:checked + figure {
        display: block;
        }

        nav[role="tab-control"] label.active {
        text-decoration: underline overline #FF3028;
        cursor: pointer;
        }

  </style>
  </head>

  <body>
"""


hintsHTML = """
<h2>Hints</h2>
    If no requests or requests older than 1 minute are listed, this means that communication between this device and the Sunny Home Manager is not working.<br>
    <a href="https://www.sunnyportal.com/Homan/ConsumerBalance">Classic Sunny Portal (Consumer Oeriew)</a><br>
    <a href="https://www.sunnyportal.com/FixedPages/HoManLive.aspx">Classic Sunny Portal (Overview of timeframes)</a>


<script id="rendered-js" >
const nodeList = document.querySelectorAll('nav[role="tab-control"] label');
const eventListenerCallback = setActiveState.bind(null, nodeList);


nodeList.forEach(node => {
  node.addEventListener("click", eventListenerCallback); /** add click event listener to all nodes */
});

/** the click handler */
function setActiveState(nodeList, event) {
  nodeList.forEach(node => {
    node.classList.remove("active"); /** remove active class from all nodes */
  });
  event.target.classList.add("active"); /* set active class on current node */
}

nodeList[0].classList.add('active'); /** add active class to first node  */

</script>

"""

tabHTML = """
<input hidden="hidden" type="radio" {check} name="tabs" id="{tabname}" />
<figure>
{data}
</figure>
"""

# see 3.2.2 UPnP Device-Description
descriptionXML = """<root xmlns="urn:schemas-upnp-org:device-1-0">
    <specVersion>
        <major>1</major>
        <minor>0</minor>
    </specVersion>
    <device>
        <deviceType>urn:schemas-simple-energy-management-protocol:device:Gateway:1</deviceType>
        <friendlyName>{friendly_name}</friendlyName>
        <manufacturer>{manufacturer}</manufacturer>
        <manufacturerURL>{manufacturer_url}</manufacturerURL>
        <modelDescription>{model_description}</modelDescription>
        <modelName>{model_name}</modelName>
        <modelNumber>{model_number}</modelNumber>
        <modelURL>{model_url}</modelURL>
        <serialNumber>{serial_number}</serialNumber>
        <UDN>uuid:{uuid}</UDN>
        <serviceList>
            <service>
                <serviceType>urn:schemas-simple-energy-management-protocol:service:NULL:1:service:NULL:1</serviceType>
                <serviceId>urn:schemas-simple-energy-management-protocol:serviceId:NULL:serviceId:NULL</serviceId>
                <SCPDURL>/XD/NULL.xml</SCPDURL>
                <controlURL>/UD/?0</controlURL>
                <eventSubURL></eventSubURL>
            </service>
        </serviceList>
        <presentationURL>{presentation_url}</presentationURL>
        <semp:X_SEMPSERVICE xmlns:semp="urn:schemas-simple-energy-management-protocol:service-1-0">
        <semp:server>{presentation_url}</semp:server>
        <semp:basePath>/semp</semp:basePath>
        <semp:transport>HTTP/Pull</semp:transport>
        <semp:exchangeFormat>XML</semp:exchangeFormat>
        <semp:wsVersion>1.1.5</semp:wsVersion>
        </semp:X_SEMPSERVICE>
    </device>
</root>
"""


sempXMLstart = """<?xml version="1.0" encoding="UTF-8"?>
<Device2EM xmlns="http://www.sma.de/communication/schema/SEMP/v1">"""

sempXMLend = """
</Device2EM>
"""

deviceInfoXML = """    <DeviceInfo>
        <Identification>
            <DeviceId>{deviceId}</DeviceId>
            <DeviceName>{deviceName}</DeviceName>
            <DeviceType>{deviceType}</DeviceType>
            <DeviceSerial>{deviceSerial}</DeviceSerial>
            <DeviceVendor>{deviceVendor}</DeviceVendor>
        </Identification>
        <Characteristics>
            <MaxPowerConsumption>{maxPowerConsumption}</MaxPowerConsumption>
            <MinPowerConsumption>{minPowerConsumption}</MinPowerConsumption>
            <MinOnTime>{minOnTime}</MinOnTime>
            <MinOffTime>{minOffTime}</MinOffTime>
        </Characteristics>
        <Capabilities>
            <CurrentPower>
                <Method>Measurement</Method>
            </CurrentPower>
            <Timestamps>
                <AbsoluteTimestamps>false</AbsoluteTimestamps>
            </Timestamps>
            <Interruptions>
                <InterruptionsAllowed>{interruptionsAllowed}</InterruptionsAllowed>
            </Interruptions>
            <Requests>
                <OptionalEnergy>{optionalEnergy}</OptionalEnergy>
            </Requests>
        </Capabilities>
    </DeviceInfo>
"""

# <!--            <MinPowerConsumption>{minPowerConsumption}</MinPowerConsumption> -->

deviceStatusXML = """        <DeviceStatus>
        <DeviceId>{deviceId}</DeviceId> <!-- {deviceName} -->
        <EMSignalsAccepted>{emSignalsAccepted}</EMSignalsAccepted>
        <Status>{status}</Status>
        <PowerConsumption>
            <PowerInfo>
                <AveragePower>{power}</AveragePower>
                <Timestamp>0</Timestamp>
                <AveragingInterval>60</AveragingInterval>
            </PowerInfo>
        </PowerConsumption>
    </DeviceStatus>
"""

timeFrameXml = """<Timeframe>
            <DeviceId>{deviceId}</DeviceId> <!-- {deviceName} -->
            <EarliestStart>{startSec}</EarliestStart> <!-- {start} -->
            <LatestEnd>{stopSec}</LatestEnd> <!-- {stop} -->
            <MinRunningTime>{minrunningtime}</MinRunningTime>
            <MaxRunningTime>{maxrunningtime}</MaxRunningTime>
        </Timeframe>
"""

# Temp             <PreferenceIndifferentAreas>NoPreference</PreferenceIndifferentAreas>


@dataclass
class callbackAction:
    deviceid: str
    shortdeviceid: str
    requestedStatus: bool
