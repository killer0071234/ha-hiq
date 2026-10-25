# Debugging

## General Steps

Check that:

1. Enable debug logging in `configuration.yaml` by adding these lines:

```yaml
logger:
  logs:
    custom_components.hiq: debug
    cybro: debug
```

`cybro` is the library that talks to the scgi server or the controller.

## Additional Debugging

If the debug logs show that a call is failing because of one of the following reasons:

- Error response from scgi server
- Timed out

## Direct connection

If a controller doesn't answer (`no answer from cXXXX`):

- Check the NAD, and that the controller runs a program (e.g. in CyPro).
- Broadcasts only reach the local network segment. For another segment or
  VLAN, enter the IP address of the controller (Reconfigure in the menu of
  the entry).
- Home Assistant in Docker needs `network_mode: host`, else enter the IP
  address.
- A firewall between Home Assistant and the controller must let UDP port
  8442 through, in both directions.
- If the controller refuses the requests, the A-bus password of the entry is
  wrong (or missing).

The debug log shows `cXXXX sent a socket from <ip>` for every socket frame
of a configured controller. If there are none although the controller sends
sockets, check the repair "UDP port 8442 is used by …" (another app holds
the port).
