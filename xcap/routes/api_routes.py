from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sipsimple.account.xcap import (Addressbook, Document, IterateItems,
                                    ResourceListsDocument, StatusIconDocument)
from sipsimple.payloads import addressbook, prescontent, resourcelists

from xcap.appusage import getApplicationForId
from xcap.authentication import AuthenticationManager
from xcap.schemas.addressbook import (AddressbookModel, BaseContactModel,
                                      BaseGroupModel, BasePolicyModel,
                                      ContactModel, GroupAddModel,
                                      GroupContactModel, GroupModel,
                                      PolicyModel)
from xcap.schemas.api_errors import (COMMON_ERRORS, CONTACT_ADD_ERRORS,
                                     GROUP_MEMBER_ADD_ERRORS,
                                     GROUP_MEMBER_ERRORS, ICON_ERRORS,
                                     error_responses)
from xcap.schemas.user import UserIconModel, UserModel
from xcap.schemas.utils import (convert_to_dict, payload_to_contact,
                                payload_to_policy)
from xcap.services.xcap_service import get_xcap_resource
from xcap.uri import XCAPUri


# Monkey patch document class
def Document_init(self):
    self.content = None


def Document_parse(self, content):
    self.content = self.payload_type.parse(content)


Document.__init__ = Document_init
Document.parse = Document_parse

router = APIRouter(prefix="/api/v1")

auth_manager = AuthenticationManager()


def make_auth_wrapper(document_provider):
    async def auth_dependency(
        request: Request,
        user: UserModel,
        document: Document = Depends(document_provider)
    ) -> XCAPUri:
        return await auth_manager.authenticate_api_request(request, document, user)

    return Depends(auth_dependency)


def get_rls_document():
    return ResourceListsDocument()


def get_status_icon_document():
    return StatusIconDocument()


def normalize(document: Document) -> Document:
    if document.content is None:
        document.content = resourcelists.ResourceLists()

    resource_lists = document.content

    try:
        oma_buddylist = resource_lists['oma_buddylist']
    except KeyError:
        oma_buddylist = resourcelists.List(name='oma_buddylist')
        resource_lists.add(oma_buddylist)
    try:
        oma_grantedcontacts = resource_lists['oma_grantedcontacts']
    except KeyError:
        oma_grantedcontacts = resourcelists.List(name='oma_grantedcontacts')
        resource_lists.add(oma_grantedcontacts)
    try:
        oma_blockedcontacts = resource_lists['oma_blockedcontacts']
    except KeyError:
        oma_blockedcontacts = resourcelists.List(name='oma_blockedcontacts')
        resource_lists.add(oma_blockedcontacts)

    try:
        dialog_grantedcontacts = resource_lists['dialog_grantedcontacts']
    except KeyError:
        dialog_grantedcontacts = resourcelists.List(name='dialog_grantedcontacts')
        resource_lists.add(dialog_grantedcontacts)
    try:
        dialog_blockedcontacts = resource_lists['dialog_blockedcontacts']
    except KeyError:
        dialog_blockedcontacts = resourcelists.List(name='dialog_blockedcontacts')
        resource_lists.add(dialog_blockedcontacts)

    try:
        sipsimple_presence_rls = resource_lists['sipsimple_presence_rls']
    except KeyError:
        sipsimple_presence_rls = resourcelists.List(name='sipsimple_presence_rls')
        resource_lists.add(sipsimple_presence_rls)
    try:
        sipsimple_dialog_rls = resource_lists['sipsimple_dialog_rls']
    except KeyError:
        sipsimple_dialog_rls = resourcelists.List(name='sipsimple_dialog_rls')
        resource_lists.add(sipsimple_dialog_rls)

    try:
        sipsimple_addressbook = resource_lists['sipsimple_addressbook']
    except KeyError:
        sipsimple_addressbook = resourcelists.List(name='sipsimple_addressbook')
        resource_lists.add(sipsimple_addressbook)

    return document


async def load_data(document: Document, url: XCAPUri, request: Request, propagate: bool = True) -> Document:
    xcap_data = get_xcap_resource(url, getApplicationForId(document.application))
    try:
        data = await xcap_data.handle_get(request)
    except Exception as e:
        if propagate:
            raise e
        return xcap_data
    document.dirty = False
    document.parse(data.body)
    return xcap_data


@router.get("/users/{user}/icon", tags=["User"])
async def get_icon(
    user: UserModel,
    request: Request,
    document: Document = Depends(get_status_icon_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_status_icon_document)
) -> UserIconModel:
    await load_data(document, xcap_uri, request)

    return UserIconModel(
        user=user,
        data=str(document.content.data),
        mime_type=str(document.content.mime_type),
        description=str(document.content.description),
        encoding=str(document.content.encoding)
    )


@router.post("/users/{user}/icon", tags=["User"], responses=ICON_ERRORS)
async def add_icon(
    user: UserModel,
    icon: UserIconModel,
    request: Request,
    document: Document = Depends(get_status_icon_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_status_icon_document)
) -> UserIconModel:
    xcap_data = await load_data(document, xcap_uri, request, False)

    content = prescontent.PresenceContent(data=icon.data, mime_type=icon.mime_type, encoding=icon.encoding, description=icon.description)
    if document.content and content and document.content.data == content.data:
        raise HTTPException(304)

    document.content = content
    request.state.body = document.content.toxml()
    await xcap_data.handle_update(request)
    return icon


@router.delete("/users/{user}/icon", tags=["User"], status_code=204, responses=COMMON_ERRORS)
async def delete_icon(
    user: UserModel,
    request: Request,
    document: Document = Depends(get_status_icon_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_status_icon_document)
) -> Response:
    xcap_data = await load_data(document, xcap_uri, request)
    request.state.body = document.content.toxml()
    response = await xcap_data.handle_update(request)
    if response.status_code == 200:
        response.status_code = 204
    return await xcap_data.handle_delete(request)


@router.get("/users/{user:path}/addressbook", tags=["Addressbook"], responses=COMMON_ERRORS)
async def read_addressbook(
    user: UserModel,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> AddressbookModel:
    await load_data(document, xcap_uri, request)
    ab = Addressbook.from_payload(document.content['sipsimple_addressbook'])
    return AddressbookModel(**convert_to_dict(ab))


@router.get("/users/{user:path}/addressbook/contacts", tags=["Addressbook", "Contacts"], responses=COMMON_ERRORS)
async def get_contacts(
    user: UserModel,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> List[ContactModel]:
    await load_data(document, xcap_uri, request)
    ab = Addressbook.from_payload(document.content['sipsimple_addressbook'])
    return AddressbookModel(**convert_to_dict(ab)).contacts


@router.get("/users/{user:path}/addressbook/contacts/{contact_id}", tags=["Addressbook", "Contacts"], responses=error_responses("contact"))
async def get_contact(
    user: UserModel,
    contact_id: str,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> ContactModel:
    await load_data(document, xcap_uri, request)

    sipsimple_addressbook = document.content['sipsimple_addressbook']
    try:
        contact = sipsimple_addressbook[addressbook.Contact, contact_id]
    except KeyError:
        raise HTTPException(404, detail="Contact not found")

    contact = payload_to_contact(contact)
    return ContactModel(**contact)


@router.post("/users/{user:path}/addressbook/contacts", tags=["Addressbook", "Contacts"], responses=CONTACT_ADD_ERRORS)
async def add_contact(
    user: UserModel,
    contact: ContactModel,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> ContactModel:
    xcap_data = await load_data(document, xcap_uri, request, False)

    if document.content is None:
        normalize(document)

    sipsimple_addressbook = document.content['sipsimple_addressbook']
    try:
        sipsimple_addressbook[addressbook.Contact, contact.id]
    except KeyError:
        pass
    else:
        raise HTTPException(409)

    presence_handling = addressbook.PresenceHandling(contact.presence.policy, contact.presence.subscribe)
    dialog_handling = addressbook.DialogHandling(contact.dialog.policy, contact.dialog.subscribe)
    xml_contact = addressbook.Contact(contact.id, contact.name, presence_handling=presence_handling, dialog_handling=dialog_handling)
    for uri in contact.uris:
        contact_uri = addressbook.ContactURI(uri.id, uri.uri, uri.type)
        contact_uri.attributes = addressbook.ContactURI.attributes.type(uri.attributes)
        xml_contact.uris.add(contact_uri)
    xml_contact.uris.default = [uri.id for uri in contact.uris if uri.default][0]
    xml_contact.attributes = addressbook.Contact.attributes.type(contact.attributes)
    sipsimple_addressbook.add(xml_contact)

    request.state.body = document.content.toxml()
    await xcap_data.handle_update(request)
    ab = payload_to_contact(xml_contact)
    return ContactModel(**convert_to_dict(ab))


@router.put("/users/{user:path}/addressbook/contacts/{contact_id}", tags=["Addressbook", "Contacts"], responses=error_responses("contact"))
async def update_contact(
    user: UserModel,
    contact_id: str,
    contact: BaseContactModel,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> ContactModel:
    xcap_data = await load_data(document, xcap_uri, request)

    sipsimple_addressbook = document.content['sipsimple_addressbook']
    try:
        ab_contact = sipsimple_addressbook[addressbook.Contact, contact_id]
    except KeyError:
        raise HTTPException(404, detail="Contact not found")

    presence_handling = addressbook.PresenceHandling(contact.presence.policy, contact.presence.subscribe)
    dialog_handling = addressbook.DialogHandling(contact.dialog.policy, contact.dialog.subscribe)
    ab_contact.name = contact.name
    ab_contact.presence_handling = presence_handling
    ab_contact.dialog_handling = dialog_handling

    for uri in contact.uris:
        contact_uri = addressbook.ContactURI(uri.id, uri.uri, uri.type)
        contact_uri.attributes = addressbook.ContactURI.attributes.type(uri.attributes)
        ab_contact.uris.add(contact_uri)
    ab_contact.uris.default = [uri.id for uri in contact.uris if uri.default][0]
    attributes = addressbook.Contact.attributes.type(contact.attributes)
    ab_contact.attributes.update(attributes)

    request.state.body = document.content.toxml()
    await xcap_data.handle_update(request)
    return ContactModel(**payload_to_contact(ab_contact))


@router.delete(
    "/users/{user:path}/addressbook/contacts/{contact_id}",
    tags=["Addressbook", "Contacts"],
    status_code=204,
    responses=error_responses("contact")
)
async def delete_contact(
    user: UserModel,
    contact_id: str,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> Response:
    xcap_data = await load_data(document, xcap_uri, request)

    sipsimple_addressbook = document.content['sipsimple_addressbook']
    for group in (group for group in sipsimple_addressbook[addressbook.Group, IterateItems] if contact_id in group.contacts):
        group.contacts.remove(contact_id)
    try:
        del sipsimple_addressbook[addressbook.Contact, contact_id]
    except KeyError:
        raise HTTPException(404, detail="Contact not found")

    request.state.body = document.content.toxml()
    response = await xcap_data.handle_update(request)
    if response.status_code == 200:
        response.status_code = 204
    return response


# Policy Routes
@router.get("/users/{user:path}/addressbook/policies", tags=["Addressbook", "Policies"], responses=COMMON_ERRORS)
async def get_policies(
    user: UserModel,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> List[PolicyModel]:
    await load_data(document, xcap_uri, request)

    ab = Addressbook.from_payload(document.content['sipsimple_addressbook'])
    return AddressbookModel(**convert_to_dict(ab)).policies


@router.get("/users/{user:path}/addressbook/policies/{policy_id}", tags=["Addressbook", "Policies"], responses=error_responses("policy"))
async def get_policy(
    user: UserModel,
    policy_id: str,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> PolicyModel:
    await load_data(document, xcap_uri, request)

    sipsimple_addressbook = document.content['sipsimple_addressbook']
    try:
        policy = sipsimple_addressbook[addressbook.Policy, policy_id]
    except KeyError:
        raise HTTPException(404, detail="Policy not found")
    policy = payload_to_policy(policy)

    return PolicyModel(**policy)


@router.post("/users/{user:path}/addressbook/policies", tags=["Addressbook", "Policies"], responses=COMMON_ERRORS)
async def add_policy(
    user: UserModel,
    policy: PolicyModel,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> PolicyModel:
    xcap_data = await load_data(document, xcap_uri, request, False)

    if document.content is None:
        normalize(document)

    sipsimple_addressbook = document.content['sipsimple_addressbook']
    presence_handling = addressbook.PresenceHandling(policy.presence.policy, policy.presence.subscribe)
    dialog_handling = addressbook.DialogHandling(policy.dialog.policy, policy.dialog.subscribe)
    xml_policy = addressbook.Policy(policy.id, policy.uri, policy.name, presence_handling=presence_handling, dialog_handling=dialog_handling)
    xml_policy.attributes = addressbook.Policy.attributes.type(policy.attributes)
    sipsimple_addressbook.add(xml_policy)

    request.state.body = document.content.toxml()
    await xcap_data.handle_update(request)

    return PolicyModel(**payload_to_policy(xml_policy))


@router.put("/users/{user:path}/addressbook/policies/{policy_id}", tags=["Addressbook", "Policies"], responses=error_responses("policy"))
async def update_policy(
    user: UserModel,
    policy_id: str,
    policy: BasePolicyModel,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> PolicyModel:
    xcap_data = await load_data(document, xcap_uri, request)

    sipsimple_addressbook = document.content['sipsimple_addressbook']
    try:
        xml_policy = sipsimple_addressbook[addressbook.Policy, policy_id]
    except KeyError:
        raise HTTPException(404, detail="Policy not found")

    presence_handling = addressbook.PresenceHandling(policy.presence.policy, policy.presence.subscribe)
    dialog_handling = addressbook.DialogHandling(policy.dialog.policy, policy.dialog.subscribe)
    xml_policy.name = policy.name
    xml_policy.uri = policy.uri
    xml_policy.presence_handling = presence_handling
    xml_policy.dialog_handling = dialog_handling
    attributes = addressbook.Policy.attributes.type(policy.attributes)
    xml_policy.attributes.update(attributes)

    request.state.body = document.content.toxml()
    await xcap_data.handle_update(request)
    return PolicyModel(**payload_to_policy(xml_policy))


@router.delete(
    "/users/{user:path}/addressbook/policies/{policy_id}",
    tags=["Addressbook", "Policies"],
    status_code=204, responses=error_responses("policy")
)
async def delete_policy(
    user: UserModel,
    policy_id: str,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> Response:
    xcap_data = await load_data(document, xcap_uri, request)

    sipsimple_addressbook = document.content['sipsimple_addressbook']
    try:
        del sipsimple_addressbook[addressbook.Policy, policy_id]
    except KeyError:
        raise HTTPException(404, detail="Policy not found")

    request.state.body = document.content.toxml()
    response = await xcap_data.handle_update(request)
    if response.status_code == 200:
        response.status_code = 204
    return response


# Group Routes
@router.get("/users/{user:path}/addressbook/groups", tags=["Addressbook", "Groups"], responses=COMMON_ERRORS)
async def get_groups(
    user: UserModel,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> List[GroupModel]:
    await load_data(document, xcap_uri, request)
    ab = Addressbook.from_payload(document.content['sipsimple_addressbook'])
    return AddressbookModel(**convert_to_dict(ab)).groups


@router.get("/users/{user:path}/addressbook/groups/{group_id}", tags=["Addressbook", "Groups"], responses=error_responses("group"))
async def get_group(
    user: UserModel,
    group_id: str,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> GroupModel:
    await load_data(document, xcap_uri, request)

    sipsimple_addressbook = document.content['sipsimple_addressbook']
    try:
        group = sipsimple_addressbook[addressbook.Group, group_id]
    except KeyError:
        raise HTTPException(404, detail="Group not found")

    ab = Addressbook.from_payload(document.content['sipsimple_addressbook'])
    return GroupModel(
        id=group_id,
        name=group.name.value,
        contacts=[convert_to_dict(ab.contacts[contact_id]) for contact_id in group.contacts],
        attributes={**group.attributes}
    )


@router.post("/users/{user:path}/addressbook/groups", tags=["Addressbook", "Groups"], responses=COMMON_ERRORS)
async def add_group(
    user: UserModel,
    group: GroupAddModel,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> GroupModel:
    xcap_data = await load_data(document, xcap_uri, request, False)

    if document.content is None:
        normalize(document)

    sipsimple_addressbook = document.content['sipsimple_addressbook']
    existing_contacts = []
    for contact in group.contacts:
        try:
            sipsimple_addressbook[addressbook.Contact, contact.id]
        except KeyError:
            continue
        existing_contacts.append(contact.id)

    xml_group = addressbook.Group(group.id, group.name, existing_contacts)
    xml_group.attributes = addressbook.Group.attributes.type(group.attributes)
    sipsimple_addressbook.add(xml_group)

    ab = Addressbook.from_payload(document.content['sipsimple_addressbook'])

    request.state.body = document.content.toxml()
    await xcap_data.handle_update(request)
    return GroupModel(
        id=group.id,
        name=group.name,
        contacts=[convert_to_dict(ab.contacts[contact_id]) for contact_id in xml_group.contacts],
        attributes={**xml_group.attributes}
    )


@router.put("/users/{user:path}/addressbook/groups/{group_id}", tags=["Addressbook", "Groups"], responses=error_responses("group"))
async def update_group(
    user: UserModel,
    group_id: str,
    group: BaseGroupModel,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> GroupModel:
    xcap_data = await load_data(document, xcap_uri, request)

    sipsimple_addressbook = document.content['sipsimple_addressbook']
    try:
        xml_group = sipsimple_addressbook[addressbook.Group, group_id]
    except KeyError:
        raise HTTPException(404, detail="Group not found")

    xml_group.name = group.name
    # xml_group.contacts = [contact.id for contact in group.contacts]
    attributes = addressbook.Group.attributes.type(group.attributes)
    xml_group.attributes.update(attributes)
    ab = Addressbook.from_payload(document.content['sipsimple_addressbook'])

    request.state.body = document.content.toxml()
    await xcap_data.handle_update(request)
    return GroupModel(
        id=group_id,
        name=group.name,
        contacts=[convert_to_dict(ab.contacts[contact_id]) for contact_id in xml_group.contacts],
        attributes={**xml_group.attributes}
    )


@router.delete(
    "/users/{user:path}/addressbook/groups/{group_id}",
    tags=["Addressbook", "Groups"],
    status_code=204,
    responses=error_responses("group")
)
async def delete_group(
    user: UserModel,
    group_id: str,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> Response:
    xcap_data = await load_data(document, xcap_uri, request)

    sipsimple_addressbook = document.content['sipsimple_addressbook']
    try:
        del sipsimple_addressbook[addressbook.Group, group_id]
    except KeyError:
        raise HTTPException(404, detail="Group not found")

    request.state.body = document.content.toxml()
    response = await xcap_data.handle_update(request)
    if response.status_code == 200:
        response.status_code = 204
    return response


@router.post(
    "/users/{user:path}/addressbook/groups/{group_id}/members",
    tags=["Addressbook", "Groups", "Members"],
    responses=GROUP_MEMBER_ADD_ERRORS
)
async def add_group_member(
    user: UserModel,
    group_id: str,
    contact: GroupContactModel,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> GroupModel:
    xcap_data = await load_data(document, xcap_uri, request)

    sipsimple_addressbook = document.content['sipsimple_addressbook']
    try:
        group = sipsimple_addressbook[addressbook.Group, group_id]
    except KeyError:
        raise HTTPException(404, detail="Group not found")

    if contact.id in group.contacts:
        raise HTTPException(status_code=409, detail="Contact already in group")

    try:
        sipsimple_addressbook[addressbook.Contact, contact.id]
    except KeyError:
        raise HTTPException(404, detail="Contact not found")

    group.contacts.add(contact.id)

    request.state.body = document.content.toxml()
    await xcap_data.handle_update(request)
    ab = Addressbook.from_payload(document.content['sipsimple_addressbook'])

    return GroupModel(
        id=group.id,
        name=group.name.value,
        contacts=[convert_to_dict(ab.contacts[contact_id]) for contact_id in group.contacts],
        attributes={**group.attributes}
    )


@router.delete(
    "/users/{user:path}/addressbook/groups/{group_id}/members/{member_id}",
    tags=["Addressbook", "Groups", "Members"],
    status_code=204,
    responses=GROUP_MEMBER_ERRORS
)
async def delete_group_member(
    user: UserModel,
    group_id: str,
    member_id: str,
    request: Request,
    document: Document = Depends(get_rls_document),
    xcap_uri: XCAPUri = make_auth_wrapper(get_rls_document)
) -> Response:
    xcap_data = await load_data(document, xcap_uri, request)

    sipsimple_addressbook = document.content['sipsimple_addressbook']
    try:
        group = sipsimple_addressbook[addressbook.Group, group_id]
    except KeyError:
        raise HTTPException(404, detail="Group not found")

    try:
        group.contacts.remove(member_id)
    except KeyError:
        raise HTTPException(404, detail="Contact not found")

    request.state.body = document.content.toxml()
    response = await xcap_data.handle_update(request)
    if response.status_code == 200:
        response.status_code = 204
    return response
