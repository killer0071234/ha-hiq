# Debugging

## General Steps

Check that:

1. Enable debug logging in `configuration.yaml` by adding these lines:

```yaml
logger:
  logs:
    custom_components.hiq: debug
```

## Additional Debugging

If the debug logs show that a call is failing because of one of the following reasons:

- Error response from scgi server
- Timed out
