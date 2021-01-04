# Demonstration Script

[![published](https://static.production.devnetcloud.com/codeexchange/assets/images/devnet-published.svg)](https://developer.cisco.com/codeexchange/github/repo/hpreston/demo_mac_to_interface_tool)

This was a fun little project to tackle here at the end of 2020.  It started with a question that I got via email.  The gist of the question was: 

> We've a need to grab the IP table off our core, and associate it with MAC addresses and interfaces on edge switches. We could do it manually with Excel, but is there an easier way? 

As with a lot of things in tech, once I dove in there were all sorts of interesting things that I learned, and questions about the workflow came up.

## Approach and Assumptions 
Here’s the general approach and assumptions I took as I put together this example script.  

1.	I wanted to create a tool that could be used across different environments, and wasn’t strongly linked to a specific network or topology. 
2.	The ask started with the ARP table from network devices, and then generated info for what switch ports the MACs known by ARP were located.  I followed this same approach in my script, so if a MAC address was found in a MAC table, but no corresponding ARP entry was found the MAC address is ignored.
    * In most cases this is probably a limited number of MACs, however in my network where I was testing, we have a large number of L2 only networks so it was an interesting side affect of my script. 
3.	I assumed there was a specific set of devices in the network that would be the Layer 3 function for where we’d check ARP tables.  This list of Layer 3 devices would be an argument to the script. 
4.	Our interest is in access ports where MAC Addresses show up, not inter-switch trunks. This meant being able to ignore or rule out cases where MAC addresses show up on trunks automatically would be handy.  I have found most network engineers use common switch interfaces (often port-channel names) as inter-switch links.  The script takes as an input a list of interface names to skip/ignore when reporting interfaces where a MAC address is found. 
    * The script also is configured to ignore interface names of "CPU", "Sup-eth1(R)", "vPC Peer-Link(R)".  For this use case these “interfaces” wouldn’t be relevant and just generate noise in the report.  
5.	The resulting data from the script is a JSON document.  I went with this as it’s a great format to allow lots of other later manipulation of the data. 

As I always like to build things to be able to share, which is why I'm posting it here. You are welcome to use it as it is, or build from it for your own needs.  But keep in mind this all important caveat: 

> ***This script is provided as an example only, and does not come with any warranty or liability for damage. Before running this script against your network, you should thoroughly test it, and understand the impacts it will have.***

## How to use the script

Suppose you want to leverage this script and test it in your lab.  This script is built using [pyATS](https://developer.cisco.com/pyats), an open source Python network automation framework from Cisco.  If you are new to pyATS, I’d encourage you to checkout the [Getting Started Guide](https://developer.cisco.com/docs/pyats-getting-started/) on DevNet.

Start out by installing pyATS in your Python virtual environment.  I've included a requirements file that has the version of pyATS I used for the project, but any newer version should work. 

```
python3.7 -m venv venv 
source venv/bin/activate 
pip install -r requirements.txt 
```

First, you’ll need to generate a Testbed for your network to get started.  A Testbed is like an inventory file from Ansible or another automation tool.  The testbed file is formatted in YAML, but can be created from an Excel/CSV file or other methods.  For full details on Testbed creation, check out [Creating Testbed YAML File](https://pubhub.devnetcloud.com/media/pyats-getting-started/docs/quickstart/manageconnections.html#creating-testbed-yaml-file)
In the documentation. 

Once you have the testbed file, you’d run the script with a command like this: 

```python
python mac_lookup.py --testbed testbed.yaml \
  --l3device leaf01-1 oob01 \
  --skipinterface "Port-channel2"
```

The parameter `--l3device` takes a list of device names from the testbed that have the ARP information the results will be built from. And `--skipinterface` would be the list of interswitch link interface names to ignore in the results. 

> Note: You can run `python mac_lookup.py --help` for details on the parameters. 

The script would run and provide output like this: 

```
Building MAC Address list from ARP information on devices leaf01-1, oob01
Looking up Layer 3 IP -> MAC Mappings.
Checking L3 device leaf01-1
Checking L3 device oob01
Looking up interfaces where MAC addresses are found on the testbed. The following interfaces will be ignored: Port-channel2
No ARP for MAC Address bcf1.f2dc.29a5 found.
No ARP for MAC Address 0050.5661.c275 found.
Saving results to file 'results.json'.
Disconnecting from all devices.
Disconnecting from leaf01-1
Disconnecting from oob01
Disconnecting from spine01-1
```

The resulting “results.json” file would have data that looks similar to this: 

```json
{
  "0050.568c.7aa1": {
    "ip": "172.19.248.55",
    "interfaces": [
      {
        "device": "spine01-1",
        "interface": "Ethernet1/7",
        "mac_type": "dynamic",
        "vlan": "41"
      }
    ]
  },
  "0050.5661.4bba": {
    "ip": "172.19.6.11",
    "interfaces": [
      {
        "device": "spine01-1",
        "interface": "Ethernet1/6",
        "mac_type": "dynamic",
        "vlan": "30"
      }
    ]
  },
  "000c.29aa.086b": {
    "ip": "172.19.6.12",
    "interfaces": [
      {
        "device": "spine01-1",
        "interface": "Ethernet1/6",
        "mac_type": "dynamic",
        "vlan": "30"
      }
    ]
  }
}
```

## How it works, a peak under the hood

I highly encourage you to read through the full script to truly understand how it works. I did my best to provide comments and examples within to help describe the flow and what is going on. This was just as much for me as for anyone else who could be interested in it.

But there are few parts of the logic and function that I think are worth discussing directly here. 

### Python argparse
I wanted to build this as a tool that anyone could use, and this typically means a CLI type utility.  I opted to leverage the standard argparse utility from Python, though there are other libraries available as well.  Click is another one I’ve used many times before for more robust tools. 

The key part of argparse is allowing users to provide inputs to the script at run time. This is seen in this part of the code: 

```python
parser.add_argument(
    "--testbed",
    dest="testbed",
    help="testbed YAML file",
    type=str,
    default=None,
)
parser.add_argument(
    "--l3device",
    dest="layer3_devices",
    help="Layer 3 Devices whose ARP tables will be gathered.",
    type=str,
    nargs="+",
)
parser.add_argument(
    "--skipinterface",
    dest="skip_interface",
    help="Interface names to skip learning MACs on. Most commonly used for known trunks.",
    type=str,
    nargs="*",
    default=[],
)
parser.add_argument(
    "--outputfile",
    dest="output_file",
    help="File to save the collected data to in JSON format.",
    type=str,
    default="results.json",
)
```


### Project flow and functions 
There are six steps to this script.

1.	Connect to all devices in the testbed file for the network 
2.	Identify which testbed devices are the “layer 3 devices” where we’ll lookup ARP information 
3.	Generate the initial MAC list (technically a Python dictionary) from the ARP tables on the Layer 3 Devices 
4.	Add in interface details for each discovered MAC address 
5.	Create the results.json file 
6.	Disconnect from all devices (we don’t want to leave open VTY line connections)

With the exception of writing out the results file, I created Python functions for each of these steps.  This allowed for modular testing of the code during development, and possibilities for future reusability.  

#### `load_testbed()`
This is a very basic function that first attempts to initialize a new Genie testbed object using the provided testbed filename.  As long as the testbed file is formatted correctly, this should succeed, but if there is an error the script will exit. 

> Tip: You can verify your testbed file with “pyats validate testbed testbed.yaml” 

It then attempts to connect to all devices in the testbed.  Should a `ConnectionError` be raised due to a device connection failing a message is written to the screen to notify the user.  

#### `discover_macs()`
This function takes the list of layer3_devices provided as input, and runs the appropriate `arp_lookup_command` for the platform using the command parsing ability in pyATS. 

I created a dictionary for the likely platforms and the appropriate command: 

```python
arp_lookup_command = {
    "nxos": "show ip arp vrf all",
    "iosxr": "show arp detail",
    "iosxe": "show ip arp",
    "ios": "show ip arp",
}
```

And then we run the appropriate command for the device using the parse method. 

```python
arp_info = device.parse(arp_lookup_command[device.os])
```

One of the main advantages of pyATS is that the parser will return not the clear text output, but rather a nice Python object we can work with.  Here is an example of what the returned data would look like

```python
{
"interfaces": {
    "Ethernet1/3": {
    "ipv4": {
        "neighbors": {
        "172.16.252.2": {
            "ip": "172.16.252.2",
            "link_layer_address": "5254.0016.18d2",
            "physical_interface": "Ethernet1/3",
            "origin": "dynamic",
            "age": "00:10:51"
        }
        }
    }
    }
},
"statistics": {
    "entries_total": 8
}
}
```

With this data from all Layer 3 devices, a straightforward use of Python loops allow the creation and return of a dictionary of MAC Addresses ready to have interfaces filled in. 

```python
{
"0050.56bf.6f29": {
    "ip": "10.10.20.49",
    "interfaces": []
},
"5254.0006.91c9": {
    "ip": "10.10.20.172",
    "interfaces": []
}
}
```

#### `lookup_interfaces()`
This function is where we find the true goal of our script, the interfaces where these MAC addresses are located.  This is done using the command parsing capabilities of pyATS with the command “show mac address-table”.  This will generate a nice Python object that looks like this: 

```python
{
  "mac_table": {
    "vlans": {
      "999": {
        "vlan": 999,
        "mac_addresses": {
          "5254.0000.c816": {
            "mac_address": "5254.0000.c816",
            "interfaces": {
              "GigabitEthernet0/3": {
                "interface": "GigabitEthernet0/3",
                "entry_type": "dynamic"
              }
            }
          }
        }
      }
    }
  },
  "total_mac_addresses": 3
}
```

A straightforward, but multi-level, set of Python loops and conditionals are used to process this data for each device in the testbed.  It looks like this. 

```python
for vlan_id, vlan in mac_address_table["mac_table"]["vlans"].items():
    for mac_address, mac_details in vlan["mac_addresses"].items():
        if mac_address in macs.keys():
            for interface in mac_details["interfaces"].values():
                if interface["interface"] not in ignored_interface_names:
                    if "mac_type" in interface.keys():
                        mac_type = interface["mac_type"]
                    elif "entry_type" in interface.keys():
                        mac_type = interface["entry_type"]
                    else:
                        mac_type = "N/A"

                    macs[mac_address]["interfaces"].append(
                        {
                            "device": device.name,
                            "interface": interface["interface"],
                            "mac_type": mac_type,
                            "vlan": vlan_id,
                        }
                    )
        else:
            print(f"No ARP for MAC Address {mac_address} found.")
```
 
Working our way through it: 
1.	We need to loop over each VLAN returned from the table.  Each MAC table entry is tied to a particular VLAN as the MAC Address Table is tied to a Layer 2 domain. 
2.	Next we’ll loop over each MAC address listed within the VLAN 
3.	The conditional `if mac_address in macs.keys():` is where we only process MAC addresses that had a corresponding ARP entry found previously. 
4.	The third loop in loops over each interface entry for the MAC address in the table.  Typically there would only be one interface listed, but the object from Genie supports cases where there could be more than one. 
5.	Next up is where we consider the list of interface names that we don’t want to consider.  These are the CPU, Supervisor, or Interswitch Links that were provided as script inputs.
6.	Once we’ve gotten through that, the interfaces list for each MAC address in our dictionary is updated to include the device, interface, MAC type, and VLAN ID where it was found.

## And done! 
I think that about covers the basics of the example.  Depending on your experience with Python, this script may seem overly simple, or possible super duper complicated.  The Python topics (loops, conditionals, functions, etc) are all straightforward.  The complexity comes from automating the process and workflow that would be done in a manual fashion.  That’s why the most important part of any project like this is starting out with a clear understanding of the scope of the goal, as well as how you might do it manually.  
