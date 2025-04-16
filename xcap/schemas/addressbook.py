
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, root_validator
from sipsimple.addressbook import unique_id


class ContactURIModel(BaseModel):
    id: Optional[str] = Field(default_factory=unique_id)
    uri: str
    type: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    default: Optional[bool] = False


class DefaultContactURIModel(BaseModel):
    id: Optional[str] = None
    uri: str
    type: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class EventHandlingModel(BaseModel):
    policy: str
    subscribe: bool


class ContactModel(BaseModel):
    id: Optional[str] = Field(default_factory=unique_id)
    name: str
    uris: List[ContactURIModel]  # A list of ContactURI objects
    dialog: EventHandlingModel = EventHandlingModel(policy='default', subscribe=False)
    presence: EventHandlingModel = EventHandlingModel(policy='default', subscribe=False)
    attributes: Optional[Dict[str, Any]] = None
    default_uri: Optional[DefaultContactURIModel] = None

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True

    @root_validator(pre=True)
    def add_default_uri(cls, values):
        uris = values.get('uris', [])
        default_uri = None
        for uri in uris:
            if uri.get('default'):
                default_uri = uri
                break
        values['default_uri'] = default_uri
        return values

    def __eq__(self, other):
        if isinstance(other, ContactModel):
            return self is other or (self.id == other.id and self.name == other.name and self.uris == other.uris and self.dialog == other.dialog and self.presence == other.presence and
                                     self.attributes == other.attributes)
        return False

    def __hash__(self):
        return hash(self.id)


class BaseContactModel(BaseModel):
    name: str
    uris: List[ContactURIModel]  # A list of ContactURI objects
    dialog: EventHandlingModel = EventHandlingModel(policy='default', subscribe=False)
    presence: EventHandlingModel = EventHandlingModel(policy='default', subscribe=False)
    attributes: Optional[Dict[str, Any]] = None
    default_uri: Optional[DefaultContactURIModel] = None

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True

    @root_validator(pre=True)
    def add_default_uri(cls, values):
        uris = values.get('uris', [])
        default_uri = None
        for uri in uris:
            if uri.get('default'):
                default_uri = uri
                break
        values['default_uri'] = default_uri
        return values

    def __eq__(self, other):
        if isinstance(other, ContactModel):
            return self is other or (self.id == other.id and self.name == other.name and self.uris == other.uris and self.dialog == other.dialog and self.presence == other.presence and
                                     self.attributes == other.attributes)
        return False

    def __hash__(self):
        return hash(self.id)


class GroupContactModel(BaseModel):
    id: str


class BaseGroupModel(BaseModel):
    name: str
    attributes: Optional[Dict[str, Any]] = None


class GroupModel(BaseModel):
    id: Optional[str] = Field(default_factory=unique_id)
    name: str
    attributes: Optional[Dict[str, Any]] = None
    contacts: List[ContactModel]


class GroupAddModel(BaseModel):
    id: Optional[str] = Field(default_factory=unique_id)
    name: str
    attributes: Optional[Dict[str, Any]] = None
    contacts: List[GroupContactModel]


class BasePolicyModel(BaseModel):
    name: str
    uri: str
    dialog: EventHandlingModel = EventHandlingModel(policy='default', subscribe=False)
    presence: EventHandlingModel = EventHandlingModel(policy='default', subscribe=False)
    attributes: Optional[Dict[str, Any]] = None


class PolicyModel(BaseModel):
    id: Optional[str] = Field(default_factory=unique_id)
    name: str
    uri: str
    dialog: EventHandlingModel = EventHandlingModel(policy='default', subscribe=False)
    presence: EventHandlingModel = EventHandlingModel(policy='default', subscribe=False)
    attributes: Optional[Dict[str, Any]] = None


class AddressbookModel(BaseModel):
    contacts: List[ContactModel]
    groups: List[GroupModel]
    policies: List[PolicyModel]
