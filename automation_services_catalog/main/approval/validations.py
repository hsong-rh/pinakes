"""Validation functions for approval groups"""

from automation_services_catalog.main.approval.exceptions import (
    DuplicatedUuidException,
    NoAppoverRoleException,
    GroupNotExistException,
)
from automation_services_catalog.main.common.models import Group
from automation_services_catalog.main.approval.models import Action
from automation_services_catalog.main.approval.services.create_action import (
    CreateAction,
)


def validate_approver_groups(group_refs, raise_error=True):
    """Validate group permissions before they are assigned to a workflow"""

    uuids = map(lambda ref: ref["uuid"], group_refs)
    if raise_error and len(set(uuids)) < len(group_refs):
        raise DuplicatedUuidException()

    return [
        _validate_approver_group_and_raise(group_ref["uuid"])
        if raise_error
        else _validate_approver_group_no_raise(
            group_ref["uuid"], group_ref["name"]
        )
        for group_ref in group_refs
    ]


def validate_and_update_approver_groups(workflow, raise_error=True):
    """Validate group permissions in a workflow"""

    workflow.group_refs = validate_approver_groups(
        workflow.group_refs, raise_error
    )
    workflow.save()


def runtime_validate_group(request):
    """Validate the group in a request before the request starts"""

    if not request.group_ref:
        return True

    group = Group.objects.filter(id=request.group_ref).first()

    if not group:
        _error_action(request, f"Group id {request.group_ref} does not exist")
        return False

    if not _can_approve(group):
        _error_action(
            request, f"Group {group.name} does not have approver role"
        )
        return False

    return True

    # TODO: should validate whether the group contains at least one member


def _can_approve(group):
    roles = [role.name for role in group.roles.all()]
    return "approval-approver" in roles or "approval-admin" in roles


def _validate_approver_group_and_raise(uuid):
    group = Group.objects.filter(id=uuid).first()

    if not group:
        raise GroupNotExistException(f"Group with id {uuid} does not exist")

    if not _can_approve(group):
        raise NoAppoverRoleException(
            f"Group {group.name} does not have approver role"
        )

    return {"name": group.name, "uuid": uuid}


def _validate_approver_group_no_raise(uuid, old_name):
    group = Group.objects.filter(id=uuid).first()

    if not group:
        message = "(Group does not exist)"
        name = old_name if message in old_name else f"{old_name} {message}"
    elif _can_approve(group):
        name = group.name
    else:
        name = f"{group.name} (No approver role)"

    return {"name": name, "uuid": uuid}


def _error_action(request, message):
    CreateAction(
        request, {"operation": Action.Operation.ERROR, "comments": message}
    ).process()
