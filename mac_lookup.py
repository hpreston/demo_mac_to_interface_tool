#! /usr/bin/env python
"""
This is an example script that generates a report of which network interfaces a MAC addres is found.

The list of MAC adddresses to lookup is determined by checking the ARP table on a provide list of Layer 3 Devices.
"""

from genie.conf import Genie
from unicon.core.errors import TimeoutError, StateMachineError, ConnectionError
from genie.metaparser.util.exceptions import SchemaEmptyParserError
import json
import sys


def disconnect(testbed):
    """disconnect

    Helper function to disconnect from all devices in a testbed
    """

    for device_name, device in testbed.devices.items():
        print(f"Disconnecting from {device.name}")
        device.disconnect()


def load_testbed(testbed_file):
    """load_testbed

    Attempt to create a Genie Testbed Object from provided testbed file and connect to all devices.
    """

    try:
        testbed = Genie.init(testbed_file)
        try:
            testbed.connect(
                learn_hostname=True,
                log_stdout=False,
                init_exec_commands=[],
                init_config_commands=[],
                connection_timeout=20,
            )
        except ConnectionError as e:
            print(e)
            # See what devices aren't connected
            for device in testbed.devices.values():
                if not device.connected:
                    print(f"{device} is NOT connected.")
        return testbed
    except Exception as e:
        print("Error: loading testbed file")
        print(e)
        sys.exit(1)


def find_layer3_devices(testbed, layer3_devices_list):
    """find_layer3_devices

    Given a testbed object, and list of device names, return a list of testbed devices of the names
    """
    layer3_devices = []

    for name in layer3_devices_list:
        if name in testbed.devices:
            layer3_devices.append(testbed.devices[name])
        else:
            print(f"Error: Device with name {name} not found in testbed.")

    return layer3_devices


def discover_macs(layer3_devices):
    """discover_macs

    Given a list of Layer 3 devices, return their ARP tables and return a dictionary of macs.

    Example return format:
        {
        "0050.56bf.6f29": {
            "ip": "10.10.20.49",
            "interfaces": []
        },
        "5254.0006.91c9": {
            "ip": "10.10.20.172",
            "interfaces": []
        },
        }

    """

    # Dictionary that will be returned
    macs = {}

    print("Looking up Layer 3 IP -> MAC Mappings.")
    for device in layer3_devices:
        print(f"Checking L3 device {device.name}")

        # What command to lookup arp info from devices
        arp_lookup_command = {
            "nxos": "show ip arp vrf all",
            "iosxr": "show arp detail",
            "iosxe": "show ip arp",
            "ios": "show ip arp",
        }

        try:
            arp_info = device.parse(arp_lookup_command[device.os])
        except Exception as e:
            print(f"Problem looking up ARP table on device {device.name}")

        # Example output of data from command
        # {
        # "interfaces": {
        #     "Ethernet1/3": {
        #     "ipv4": {
        #         "neighbors": {
        #         "172.16.252.2": {
        #             "ip": "172.16.252.2",
        #             "link_layer_address": "5254.0016.18d2",
        #             "physical_interface": "Ethernet1/3",
        #             "origin": "dynamic",
        #             "age": "00:10:51"
        #         }
        #         }
        #     }
        #     }
        # },
        # "statistics": {
        #     "entries_total": 8
        # }
        # }

        # From returned ARP data, review the details and extract the details for returned mac dictionary
        for interface, details in arp_info["interfaces"].items():
            # print(f"  Interface {interface}")

            # For each neighbor device on an interface, add new key to macs dictionary.
            # Value for each mac will be a dictionary with keys for IP address and empty list of interfaces
            # The interfaces list will be filled in by MAC Address Table lookups
            for neighbor in details["ipv4"]["neighbors"].values():
                # print(f'{neighbor["ip"]}, {neighbor["link_layer_address"]}')
                if neighbor["link_layer_address"] != "INCOMPLETE":
                    macs[neighbor["link_layer_address"]] = {
                        "ip": neighbor["ip"],
                        "interfaces": [],
                    }

    return macs


def lookup_interfaces(macs, testbed, skip_interfaces=[]):
    """lookup_interfaces

    Given a dictionary of macs and a testbed, update the list of interfaces for each MAC Address
    with interfaces in the testbed where the MAC address is connected.

    Optional parameter:
        skip_interfaces : A list of interface names to NOT include in interface lists for macs

    Example returned value:
        {
        "0050.56bf.6f29": {
            "ip": "10.10.20.49",
            "interfaces": [
            {
                "device": "sw01-1",
                "interface": "Ethernet1/11",
                "mac_type": "dynamic",
                "vlan": "30"
            }
            ]
        },
        "5254.0006.91c9": {
            "ip": "10.10.20.172",
            "interfaces": [
            {
                "device": "sw01-1",
                "interface": "Ethernet1/12",
                "mac_type": "dynamic",
                "vlan": "30"
            }
            ]
        },
        }

    """

    # Common Interface names to ignore for recording into table
    ignored_interface_names = ["CPU", "Sup-eth1(R)", "vPC Peer-Link(R)"]

    # Combine common list with specified skip_interfaces
    ignored_interface_names += skip_interfaces

    for device in testbed.devices.values():
        try:
            mac_address_table = device.parse("show mac address-table")
        except Exception as e:
            print(
                f"Unable to retrieve MACs from device {device.name}. Likely missing parser for 'show mac address-table' or trying to lookup on router and not switch"
            )
            continue

        # Example data returned from show mac address-table command
        # {
        #   "mac_table": {
        #     "vlans": {
        #       "999": {
        #         "vlan": 999,
        #         "mac_addresses": {
        #           "5254.0000.c816": {
        #             "mac_address": "5254.0000.c816",
        #             "interfaces": {
        #               "GigabitEthernet0/3": {
        #                 "interface": "GigabitEthernet0/3",
        #                 "entry_type": "dynamic"
        #               }
        #             }
        #           }
        #         }
        #       }
        #     }
        #   },
        #   "total_mac_addresses": 3
        # }

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

    return macs


if __name__ == "__main__":
    # for stand-alone execution
    import argparse
    from pyats import topology

    parser = argparse.ArgumentParser(description="Demonstration Script")
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

    # do the parsing
    args = parser.parse_args()

    # Create object from provided file
    print(f"Attempting to load and connect to devices in testbed named {args.testbed}.")
    testbed = load_testbed(args.testbed)

    # Create list of tesbed devices to use as Layer 3 ARP sources
    layer3_devices = find_layer3_devices(testbed, args.layer3_devices)

    # Get dictionary of MAC Addresses from ARP tables in layer3 devices
    print(
        f"Building MAC Address list from ARP information on devices {', '.join(args.layer3_devices)}"
    )
    macs = discover_macs(layer3_devices)

    # Update the macs dictionary by finding the Layer 2 Interfaces where the MAC addresses are located across the testbed
    print(
        f"Looking up interfaces where MAC addresses are found on the testbed. The following interfaces will be ignored: {', '.join(args.skip_interface) }"
    )
    macs = lookup_interfaces(macs, testbed, skip_interfaces=args.skip_interface)

    print(f"Saving results to file '{args.output_file}'.")
    with open(args.output_file, "w") as f:
        f.write(json.dumps(macs, indent=2))

    # Disconnect
    print("Disconnecting from all devices.")
    disconnect(testbed)
