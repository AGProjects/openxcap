from pydantic import BaseModel
from sipsimple.account.xcap import (Contact, ContactURI, ContactURIList,
                                    EventHandling, ItemCollection, Policy)
from sipsimple.payloads.datatypes import AnyURI


def convert_to_dict(obj):
    """Recursively convert an object (including nested ones) to a Pydantic-friendly dictionary."""
    if obj is None or isinstance(obj, (str, int, float, bool, AnyURI)):
        return obj  # Return primitives and None as-is
    if isinstance(obj, list):
        return [convert_to_dict(item) for item in obj]  # Convert lists
    if isinstance(obj, ItemCollection):
        if hasattr(obj, 'default') and obj.default is not None:
            return list(map(lambda item: {**convert_to_dict(item), 'default': item.id == obj.default}, obj))
        return [convert_to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {key: convert_to_dict(value) for key, value in obj.items()}  # Convert dict values
    if isinstance(obj, BaseModel):
        return obj.model_dump()  # Convert existing Pydantic objects to dict
    if hasattr(obj, "__dict__"):
        return {key: convert_to_dict(getattr(obj, key)) for key in vars(obj) if not key.startswith("_")}
    return obj


def payload_to_contact(payload):
    uris = ContactURIList((ContactURI(uri.id, uri.uri, uri.type, **(uri.attributes or {})) for uri in payload.uris), default=payload.uris.default)
    presence_handling = EventHandling(payload.presence.policy.value, payload.presence.subscribe.value)
    dialog_handling = EventHandling(payload.dialog.policy.value, payload.dialog.subscribe.value)
    contact = Contact(payload.id, payload.name.value, uris, presence_handling, dialog_handling, **(payload.attributes or {}))
    return convert_to_dict(contact)


def payload_to_policy(payload):
    presence_handling = EventHandling(payload.presence.policy.value, payload.presence.subscribe.value)
    dialog_handling = EventHandling(payload.dialog.policy.value, payload.dialog.subscribe.value)
    policy = Policy(payload.id, payload.uri, payload.name.value, presence_handling, dialog_handling, **(payload.attributes or {}))
    return convert_to_dict(policy)
