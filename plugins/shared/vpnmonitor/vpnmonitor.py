

import logging
import godfingerEvent
import pluginExports
import lib.shared.serverdata as serverdata
import lib.shared.config as config
import os
import database
import lib.shared.client as client
import requests
import ipaddress
from lib.shared.instance_config import get_instance_config_path

SERVER_DATA = None
Log = logging.getLogger(__name__)

CONFIG_FALLBACK = """{
    "apikey":"your_api_key",
    "block":[1, 2],
    "action":0,
    "whitelist":["127.0.0.1"],
    "blacklist":[],
    "svsayOnAction": true
}"""

PluginInstance = None


class VPNMonitor:
    def __init__(self, serverData: serverdata.ServerData):
        self._status = 0
        self._serverData = serverData
        config_path = get_instance_config_path("vpnmonitor", serverData)
        self.config = config.Config.fromJSON(config_path, CONFIG_FALLBACK)
        self._messagePrefix = "^9[VPN]^7: "
        if self.config.cfg["apikey"] == "your_api_key":
            self._status = -1
            Log.error("Please specify valid api key in vpnmonitorCfg.json")

        self._database: database.ADatabase = None
        dbPath = os.path.join(os.path.dirname(__file__), "vpn.db")
        dbRes = self._serverData.API.CreateDatabase(dbPath, "vpnmonitor")
        if dbRes == database.DatabaseManager.DBM_RESULT_ALREADY_EXISTS or dbRes == database.DatabaseManager.DBM_RESULT_OK:
            self._database = self._serverData.API.GetDatabase("vpnmonitor")
            self._database.ExecuteQuery("""CREATE TABLE IF NOT EXISTS iplist (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        ip varchar(30),
                                        vpn int,
                                        date DATETIME DEFAULT CURRENT_TIMESTAMP
                                        );""")
        else:
            Log.error("Failed to create database at %s with code %d", dbPath, dbRes)
            self._status = -1


    def Start(self) -> bool:
        allClients = self._serverData.API.GetAllClients()
        for cl in allClients:
            vpnType = self.GetIpVpnType(cl.GetIp())
            self.ProcessVpnClient(cl, vpnType)
        if self._status == 0:
            return True
        else:
            return False


    def Finish(self):
        pass


    def OnClientConnect(self, client: client.Client, data: dict) -> bool:
        vpnType = self.GetClientVPNType(client)
        if vpnType < 0:
            return False
        self.ProcessVpnClient(client, vpnType)
        return False

    def GetClientVPNType(self, client: client.Client) -> int:
        ip = client.GetIp()
        return self.GetIpVpnType(ip)

    def _IsIpMatch(self, ip: str, item) -> bool:
        try:
            target_ip = ipaddress.ip_address(ip)
            if isinstance(item, str):
                return target_ip == ipaddress.ip_address(item)
            elif isinstance(item, list) and len(item) == 2:
                start_ip = ipaddress.ip_address(item[0])
                end_ip = ipaddress.ip_address(item[1])
                return start_ip <= target_ip <= end_ip
        except Exception as e:
            Log.error(f"Error checking IP {ip} against {item}: {e}")
        return False

    def GetIpVpnType(self, ip : str ) -> int:
        whitelist = self.config.cfg["whitelist"];
        for entry in whitelist:
            if self._IsIpMatch(ip, entry):
                Log.debug("IP %s matches whitelist entry %s, skipping VPN check.", ip, str(entry));
                return -1;
    
        Log.debug("Getting vpn associated with ip address %s", ip);
        existing = self._database.ExecuteQuery("SELECT vpn FROM iplist WHERE ip=\""+ip+"\"", True);
        vpnType = -1;
        if existing == None or len(existing) == 0:
            # not in the database, lets check on VPN detection service
            payload = {'key': self.config.cfg["apikey"]};
            webRequest = requests.get(f"http://v2.api.iphub.info/ip/{ip}", params = payload);
            if webRequest.status_code == 200:
                jsonified = webRequest.json();
                if "block" in jsonified:
                    vpnType = jsonified["block"];
                    fmt = "INSERT INTO iplist (ip, vpn) VALUES (%s, %d);" % ("\""+ip+"\"", vpnType);
                    self._database.ExecuteQuery(fmt);
            else:
                Log.error("Web request to VPN check service is failed with http code %d", webRequest.status_code);
        else:
            Log.debug("VPN ip entry existing in database, using it.");
            vpnType = existing[0][0];
        
        return vpnType;

    def ProcessVpnClient(self, client : client.Client, vpnType : int):
        ip = client.GetIp()
        id = client.GetId()
        blockable = self.config.GetValue("block", []);
        if vpnType in blockable:
            Log.debug("Kicking a player with ip %s due to VPN block rules" % ip);
            if self.config.GetValue("action", 0) == 1:
                Log.debug("Banning ip %s" % ip)
                self._serverData.interface.ClientBan(ip);
            self._serverData.interface.ClientKick(id);
            if self.config.cfg["svsayOnAction"] == True:
                self._serverData.interface.SvSay(self._messagePrefix + f"Kicked player {client.GetName()}^7 for suspected VPN usage.")
            return;
        
        blacklist = self.config.cfg["blacklist"];
        for entry in blacklist:
            if self._IsIpMatch(ip, entry):
                Log.debug("Kicking a player with ip %s due to VPN blacklist match: %s", ip, str(entry));
                if self.config.GetValue("action", 0) == 1:
                    Log.debug("Banning ip %s" % ip)
                    self._serverData.interface.ClientBan(ip);
                elif self.config.GetValue("action", 0) == 0:
                    Log.debug("Kicking ip %s" % ip)
                    self._serverData.interface.ClientKick(id);
                if self.config.cfg["svsayOnAction"] == True:
                    self._serverData.interface.SvSay(self._messagePrefix + f"Kicked player {client.GetName()}^7 for suspected VPN usage.")
                return;

    def OnClientDisconnect(self, client : client.Client, reason, data ) -> bool:
        return False;


# Called once when this module ( plugin ) is loaded, return is bool to indicate success for the system
def OnInitialize(serverData : serverdata.ServerData, exports = None) -> bool:
    global SERVER_DATA;
    SERVER_DATA = serverData; # keep it stored
    global PluginInstance;
    PluginInstance = VPNMonitor(serverData);
    if exports != None:
        pass;
    return True; # indicate plugin load success

# Called once when platform starts, after platform is done with loading internal data and preparing
def OnStart():
    global PluginInstance;
    from time import time
    startTime = time()
    result = PluginInstance.Start()
    if result:
        loadTime = time() - startTime
        PluginInstance._serverData.interface.SvSay(
            PluginInstance._messagePrefix + f"VPN Monitor started in {loadTime:.2f} seconds!"
        )
    return result

# Called each loop tick from the system, TODO? maybe add a return timeout for next call
def OnLoop():
    pass
    #print("Calling Loop function from plugin!");

# Called before plugin is unloaded by the system, finalize and free everything here
def OnFinish():
    pass;

# Called from system on some event raising, return True to indicate event being captured in this module, False to continue tossing it to other plugins in chain
def OnEvent(event) -> bool:
    global PluginInstance;
    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        if event.isStartup:
            return False; #Ignore startup messages
        else:
            return PluginInstance.OnClientConnect(event.client, event.data);
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENT_BEGIN:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
        if event.isStartup:
            return False; #Ignore startup messages
        else:
            return PluginInstance.OnClientDisconnect(event.client, event.reason, event.data);
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_INIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SHUTDOWN:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_KILL:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_PLAYER:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_EXIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MAPCHANGE:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMSAY:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_POST_INIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_REAL_INIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_PLAYER_SPAWN:
        return False;
    return False;

if __name__ == "__main__":
    print("This is a plugin for the Godfinger Movie Battles II plugin system. Please run one of the start scripts in the start directory to use it. Make sure that this python module's path is included in godfingerCfg!")
    input("Press Enter to close this message.")
    exit()