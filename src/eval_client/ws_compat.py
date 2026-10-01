"""Validate client options against the XPolicyLab version in a runtime image."""

import inspect


def compatible_client_kwargs(client_type, **kwargs):
    """Omit default keepalive options on clients predating those parameters.

    Older images use their own keepalive defaults. Custom values must be
    supported explicitly; never discard them or unrelated constructor options.
    This function does not connect and can run before initializing a policy.
    """
    signature = inspect.signature(client_type)
    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    omitted = []
    for name in ("ws_ping_interval_s", "ws_ping_timeout_s"):
        if name not in kwargs or name in signature.parameters or accepts_kwargs:
            continue
        if kwargs[name] != 20.0:
            raise ValueError(
                f"installed XPolicyLab client does not support {name}={kwargs[name]!r}; "
                "use its default (20.0) or an image with a newer client"
            )
        del kwargs[name]
        omitted.append(name)
    signature.bind(**kwargs)
    if omitted:
        print("[ws_compat] using installed XPolicyLab defaults for " + ", ".join(omitted))
    return kwargs
