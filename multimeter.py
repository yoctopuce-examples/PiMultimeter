#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys,re,socket,linecache
import yoctopuce

from yoctopuce.yocto_api import *
from yoctopuce.yocto_display import *
from yoctopuce.yocto_anbutton import *
from yoctopuce.yocto_voltage import *
from yoctopuce.yocto_current import *
from yoctopuce.yocto_power import *
from yoctopuce.yocto_temperature import *
from yoctopuce.yocto_lightsensor import *
from yoctopuce.yocto_pressure import *
from yoctopuce.yocto_humidity import *

# List of sensors to display (discovered by Plug-and-play)
sensors = { }
currentSensor = ""

def refreshDisplay():
    global currentSensor
    if currentSensor not in sensors:
        currentSensor = sensors.keys()[-1]
    sensor = sensors[currentSensor]
    dispLayer.clear()
    dispLayer.selectFont("Small.yfm")
    dispLayer.drawText(0,0,YDisplayLayer.ALIGN.TOP_LEFT,sensor["name"])
    dispLayer.selectFont("Medium.yfm")
    dispLayer.drawText(127,28,YDisplayLayer.ALIGN.BOTTOM_RIGHT,sensor["val"])
    display.copyLayerContent(1,2)

def deviceArrival(m):
    global sensors, currentSensor
    for i in range(m.functionCount()):
        fctName = m.functionId(i)
        fctType = re.sub("\d+$", "", fctName)
        hwId = m.get_serialNumber() + "." + fctName
        yocto_mod = getattr(yoctopuce, "yocto_"+fctType.lower(), None)
        if(yocto_mod is not None):
            className = fctType[0].upper()+fctType[1:]
            print(className+": "+fctType)
            YClass = getattr(yocto_mod, "Y"+className)
            yFind = getattr(YClass, "Find"+className)
            fct = yFind(hwId)
            if getattr(fct, "get_unit", None) is not None:
                currentSensor = fct.get_hardwareId()
                sensors[currentSensor] = \
                    { "name" : fct.get_friendlyName(),
                      "val"  : fct.get_unit() }
                fct.registerValueCallback(sensorChanged)
    refreshDisplay()

def sensorChanged(fct,value):
    hwId = fct.get_hardwareId()
    if hwId in sensors: sensors[hwId]['val'] = value+" "+fct.get_unit()
    refreshDisplay()

def deviceRemoval(m):
    deletePattern = m.get_serialNumber()+"\..*"
    deleteList = []
    for key in sensors:
        if re.match(deletePattern, key): deleteList.append(key)
    for key in deleteList:
        del sensors[key]
    refreshDisplay()

def buttonPressed(fct,value):
    global currentSensor
    if(int(value) > 500):    # button released
        fct.set_userData(False)
        return
    if(fct.get_userData()): # button was already pressed
        return
    # Button was pressed, cycle through sensors values
    fct.set_userData(True)
    delta = (1 if fct.get_hardwareId()[-1] == '1' else -1)
    if(delta != 0):
        keys = sensors.keys()
        idx = len(keys)-1
        for i in range(len(keys)):
            if keys[i] == currentSensor:
                idx = (i+delta+len(keys)) % len(keys)
        currentSensor = keys[idx]
        refreshDisplay()

def findMyIP():
    with open("/etc/resolv.conf", "r") as f:
        dns = re.sub("[^\d\.]", "", f.readlines()[-1])
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((dns, 8000))
    ipAddress = s.getsockname()[0]
    s.close()
    return ipAddress

# Setup the API to use the local VirtualHub
errmsg=YRefParam()
if YAPI.RegisterHub("127.0.0.1", errmsg) != YAPI.SUCCESS:
    sys.exit("Init error: "+errmsg.value)

# Get the display object
display = YDisplay.FirstDisplay()
if display is None:
    sys.exit("Display not connected")
display.resetAll()
dispLayer = display.get_displayLayer(1)
dispLayer.hide()

# Get the buttons objects
serial = display.get_module().get_serialNumber()
prevButton = YAnButton(serial+".anButton1")
nextButton = YAnButton(serial+".anButton6")
prevButton.set_userData(False)
nextButton.set_userData(False)
prevButton.registerValueCallback(buttonPressed);
nextButton.registerValueCallback(buttonPressed);

# Put the Raspberry Pi itself as default sensor, to show IP address
sensors[""] = { "name" : socket.gethostname(),
                "val"  : findMyIP() }
print("Host: "+socket.gethostname())
print("IP: "+findMyIP())
refreshDisplay()

# Handle sensors plug-and-play events
YAPI.RegisterDeviceArrivalCallback(deviceArrival)
YAPI.RegisterDeviceRemovalCallback(deviceRemoval)
print('Hit Ctrl-C to Stop')
while True:
    YAPI.UpdateDeviceList(errmsg) # handle plug/unplug events
    YAPI.Sleep(500, errmsg)       # handle others events
