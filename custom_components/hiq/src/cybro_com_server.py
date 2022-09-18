#!/usr/bin/python
import configparser
import http.client
import os
import ssl
import sys
import xml.etree.ElementTree as ET

from .constants import CONFIG_FILE

REMOTE_ADDR = "localhost"
REMOTE_PORT = 4000

config = configparser.ConfigParser()
config.read(CONFIG_FILE)
ssl_enabled = config.getboolean("SCGI", "tls_enabled", fallback=False)


def extract_data_from_xml(xml_text):
    data_tree = ET.fromstring(xml_text)
    results = {}

    for var_el in data_tree:
        name_el = var_el.find("name")
        value_el = var_el.find("value")
        var_name = name_el.text
        var_value = value_el.text
        description_el = var_el.find("description")
        if description_el is not None:
            var_description = description_el.text
            results[var_name] = f"Value: {var_value}", f"Description: {var_description}"

        else:
            results[var_name] = f"Value: {var_value}"

    return results


if __name__ == "__main__":
    # assume command line if environment variable is not set
    scheme = "http//:"
    query_str = os.environ.get("QUERY_STRING")
    if query_str is not None:
        # cgi request, read query string from environment variables
        remote_addr = os.environ.get("REMOTE_ADDR")
        remote_port = os.environ.get("REMOTE_PORT")
        request_uri = os.environ.get("REQUEST_URI")
    else:
        # command line, use first parameter as query string and default for others
        if len(sys.argv) <= 1:
            print("Error: query string is empty")
            quit()

        query_string = sys.argv[1]
        remote_addr = REMOTE_ADDR
        remote_port = f"{REMOTE_PORT}"
        request_uri = f"?{query_string}"

    try:
        if ssl_enabled:
            ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            ssl_context.load_cert_chain("tls/private.crt", "tls/private.key")
            connection = http.client.HTTPSConnection(
                remote_addr, int(remote_port), context=ssl_context
            )
        else:
            connection = http.client.HTTPConnection(remote_addr, int(remote_port))

        connection.request("GET", request_uri)
        response = connection.getresponse()
        result = response.read()
        connection.close()
        data = extract_data_from_xml(result)
        for var_name, value in data.items():
            print(f"Name: {var_name}")

            if isinstance(value, tuple):
                # contains both variable value and description
                for element in value:
                    print(element)
            else:
                # contains only variable value
                print(value)
            print()

    except ConnectionError:
        print(f"Error: SCGI server at {remote_addr}:{remote_port} not responding.")
        quit()
